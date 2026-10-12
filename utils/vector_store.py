
import re
import numpy as np
import faiss

from database import connect_db
from model.embedding import get_embedding


# One index per username. Document chunks remain stored in SQLite.
_user_indexes = {}


# --------------------------------------------------
# Text cleaning and tokenization
# --------------------------------------------------

def _normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def _tokenize(text):
    return set(re.findall(r"\b[a-zA-Z0-9+#.]+\b", str(text or "").lower()))


def split_text(text, chunk_size=180, overlap=40):
    """Split text into overlapping word chunks."""
    text = str(text or "").strip()

    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunk_size = max(1, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size - 1))
    step = chunk_size - overlap

    chunks = []

    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size]).strip()

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(words):
            break

    return chunks


# --------------------------------------------------
# Query understanding
# --------------------------------------------------

def _expand_query(query):
    """
    Add useful search terms for common question types.
    The original question is preserved.
    """
    q = _normalize_text(query)

    profile_phrases = (
        "tell me about myself",
        "tell me about me",
        "about myself",
        "who am i",
        "my profile",
        "my background",
        "summarize my resume",
        "summarise my resume",
        "my skills",
    )

    internship_phrases = (
        "my internship",
        "internship name",
        "internship project",
        "swizosoft",
        "internship technologies",
        "internship experience",
    )

    if any(phrase in q for phrase in profile_phrases):
        return (
            query
            + " name education degree university "
              "skills technical skills experience internship "
              "projects certifications achievements"
        )

    if any(phrase in q for phrase in internship_phrases):
        return (
            query
            + " Swizosoft Data Science Generative AI "
              "RAG retrieval pipeline BERT embeddings FAISS "
              "project technologies responsibilities"
        )

    return query


# --------------------------------------------------
# Embeddings
# --------------------------------------------------

def _embed_texts(texts):
    if not texts:
        return np.empty((0, 0), dtype="float32")

    vectors = []

    for text in texts:
        embedding = get_embedding(text)

        vector = np.asarray(
            embedding,
            dtype="float32"
        ).reshape(-1)

        if vector.size == 0:
            raise ValueError("The embedding model returned an empty vector.")

        vectors.append(vector)

    dimensions = {vector.shape[0] for vector in vectors}

    if len(dimensions) != 1:
        raise ValueError("Embedding vectors have inconsistent dimensions.")

    matrix = np.vstack(vectors).astype("float32")
    faiss.normalize_L2(matrix)

    return matrix


# --------------------------------------------------
# Cache management
# --------------------------------------------------

def invalidate_user_index(username):
    if username is not None:
        _user_indexes.pop(str(username), None)


def invalidate_all_indexes():
    _user_indexes.clear()


# --------------------------------------------------
# Save document chunks
# --------------------------------------------------

def save_document_chunks(document_id, pages):
    """
    Save extracted PDF pages or DOCX sections to SQLite.
    Replaces existing chunks for this document.
    """
    conn = connect_db()

    try:
        document = conn.execute(
            """
            SELECT id, username
            FROM documents
            WHERE id = ?
            """,
            (document_id,)
        ).fetchone()

        if document is None:
            raise ValueError(
                f"Document ID {document_id} was not found."
            )

        username = document["username"]
        prepared_chunks = []
        chunk_index = 0

        for page_item in pages or []:
            if isinstance(page_item, dict):
                page_text = (
                    page_item.get("text")
                    or page_item.get("content")
                    or ""
                )
                page_number = page_item.get(
                    "page",
                    page_item.get("page_number")
                )
            else:
                page_text = str(page_item or "")
                page_number = None

            page_text = str(page_text).strip()

            if not page_text:
                continue

            for chunk in split_text(page_text):
                prepared_chunks.append(
                    (
                        document_id,
                        chunk_index,
                        page_number,
                        chunk
                    )
                )
                chunk_index += 1

        conn.execute(
            "DELETE FROM document_chunks WHERE document_id = ?",
            (document_id,)
        )

        if prepared_chunks:
            conn.executemany(
                """
                INSERT INTO document_chunks
                    (document_id, chunk_index, page, text)
                VALUES (?, ?, ?, ?)
                """,
                prepared_chunks
            )

        conn.commit()
        invalidate_user_index(username)

        return len(prepared_chunks)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# --------------------------------------------------
# Build a per-user index
# --------------------------------------------------

def _load_user_index(username):
    conn = connect_db()

    try:
        rows = conn.execute(
            """
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                dc.chunk_index,
                dc.page,
                dc.text,
                d.filename,
                d.username
            FROM document_chunks AS dc
            INNER JOIN documents AS d
                ON d.id = dc.document_id
            WHERE d.username = ?
            ORDER BY dc.document_id, dc.chunk_index
            """,
            (username,)
        ).fetchall()

    finally:
        conn.close()

    if not rows:
        _user_indexes[username] = {
            "index": None,
            "chunks": [],
            "embeddings": None
        }
        return _user_indexes[username]

    chunks = [dict(row) for row in rows]
    texts = [chunk["text"] for chunk in chunks]
    embeddings = _embed_texts(texts)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    _user_indexes[username] = {
        "index": index,
        "chunks": chunks,
        "embeddings": embeddings
    }

    return _user_indexes[username]


# --------------------------------------------------
# Hybrid retrieval
# --------------------------------------------------

def _keyword_score(query_tokens, chunk_text):
    """
    Keyword overlap score from 0 to 1.
    Useful for names, technology names and exact terminology.
    """
    chunk_tokens = _tokenize(chunk_text)

    if not query_tokens or not chunk_tokens:
        return 0.0

    matched = query_tokens.intersection(chunk_tokens)

    return len(matched) / len(query_tokens)


def _profile_bonus(query, chunk_text):
    """
    Small ranking bonus for relevant profile sections.
    This changes ranking only; it does not create factual content.
    """
    q = _normalize_text(query)
    text = _normalize_text(chunk_text)

    profile_phrases = (
        "tell me about myself",
        "tell me about me",
        "about myself",
        "who am i",
        "my profile",
        "my background",
        "summarize my resume",
        "summarise my resume",
    )

    if any(phrase in q for phrase in profile_phrases):
        terms = (
            "education", "experience", "intern", "skills",
            "project", "certification", "bachelor", "degree",
            "python", "machine learning", "generative ai"
        )

        matched = sum(term in text for term in terms)

        return min(matched * 0.015, 0.12)

    return 0.0


def search(query, k=5, min_score=0.25, username="guest"):
    """
    Search only the selected user's documents using a combination
    of semantic similarity and keyword overlap.

    Each result contains:
        chunk_id, document_id, text, filename, page, score
    """
    query = str(query or "").strip()
    username = str(username or "guest").strip()

    if not query:
        return []

    try:
        k = max(1, int(k))
        min_score = float(min_score)
    except (TypeError, ValueError):
        k = 5
        min_score = 0.25

    cached = _user_indexes.get(username)

    if cached is None:
        cached = _load_user_index(username)

    if cached["index"] is None or not cached["chunks"]:
        return []

    # Embed the original question for semantic relevance.
    query_vector = _embed_texts([query])

    if query_vector.shape[1] != cached["index"].d:
        raise ValueError(
            "Query embedding dimensions do not match the document index."
        )

    # Calculate semantic similarity against all indexed chunks.
    semantic_scores = (
        cached["embeddings"] @ query_vector[0]
    )

    # Add keyword matching using expanded search terms.
    expanded_query = _expand_query(query)
    query_tokens = _tokenize(expanded_query)

    ranked = []

    for position, chunk in enumerate(cached["chunks"]):
        semantic_score = float(semantic_scores[position])

        keyword_score = _keyword_score(
            query_tokens,
            chunk.get("text", "")
        )

        profile_bonus = _profile_bonus(
            query,
            chunk.get("text", "")
        )

        # Weighted hybrid score. Keep semantic matching dominant.
        combined_score = (
            0.70 * semantic_score
            + 0.30 * keyword_score
            + profile_bonus
        )

        ranked.append(
            (combined_score, semantic_score, position)
        )

    ranked.sort(key=lambda item: item[0], reverse=True)

    results = []
    seen_texts = set()
    seen_document_chunks = set()

    for combined_score, semantic_score, position in ranked:
        if combined_score < min_score:
            continue

        chunk = cached["chunks"][position]
        normalized = _normalize_text(chunk.get("text", ""))

        if not normalized:
            continue

        # Collapse exact duplicates from duplicate uploads.
        if normalized in seen_texts:
            continue

        identity = (
            chunk.get("document_id"),
            chunk.get("chunk_index")
        )

        if identity in seen_document_chunks:
            continue

        seen_texts.add(normalized)
        seen_document_chunks.add(identity)

        results.append({
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "text": chunk["text"],
            "filename": chunk["filename"],
            "page": chunk["page"],
            "score": float(combined_score)
        })

        if len(results) >= k:
            break

    return results

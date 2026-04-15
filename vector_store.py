import faiss
import numpy as np
from model.embedding import get_embedding

documents = []
index = None


# -------- TEXT SPLITTING --------
def split_text(text, chunk_size=200):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)

    return chunks


# -------- STORE DOCUMENT --------
def store_documents(text):
    global documents, index

    documents = split_text(text)

    vectors = []

    for chunk in documents:
        emb = get_embedding(chunk).numpy()[0]
        vectors.append(emb)

    vectors = np.array(vectors).astype('float32')

    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)


# -------- SEARCH --------
def search(query, k=5):
    global index, documents

    if index is None:
        return "No PDF uploaded yet."

    query_vec = get_embedding(query).numpy().astype('float32')

    D, I = index.search(query_vec, k)

    # Filter results by keyword match
    results = []
    query_words = query.lower().split()

    for i in I[0]:
        chunk = documents[i].lower()

        # Check if any keyword present
        if any(word in chunk for word in query_words):
            results.append(documents[i])

    # If nothing matched → fallback to top result
    if not results:
        results = [documents[I[0][0]]]

    return " ".join(results[:3])

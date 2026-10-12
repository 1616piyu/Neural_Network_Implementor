import json
import os
import re
import secrets
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from database import create_tables, connect_db
from utils.pdf_handler import extract_document
from utils.vector_store import save_document_chunks, search
from utils.generator import generate_answer, _is_document_question


# --------------------------------------------------
# Application configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
GUEST_QUESTION_LIMIT = 5

app = Flask(__name__)

# Configure SECRET_KEY in your deployment environment.
# The fallback is for local development only and changes on restart.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", "").lower()
    in {"1", "true", "yes"}
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

create_tables()


# --------------------------------------------------
# Database compatibility migration
# --------------------------------------------------

def migrate_user_schema():
    """Add full_name without deleting existing users or data."""
    conn = connect_db()

    try:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }

        if "full_name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT")

        conn.commit()
    finally:
        conn.close()


migrate_user_schema()


# --------------------------------------------------
# Utility functions
# --------------------------------------------------

def allowed_file(filename):
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def normalize_username(username):
    return str(username or "").strip()


def normalize_email(email):
    return str(email or "").strip().lower()


def valid_email(email):
    """Basic email-format validation; does not verify email ownership."""
    if not email or len(email) > 254:
        return False

    pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
        r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
    )
    return bool(re.fullmatch(pattern, email))


def get_authenticated_username():
    """Return the username established by a successful server-side login."""
    username = session.get("username")
    return username if isinstance(username, str) and username else None


def is_guest_session():
    return session.get("is_guest") is True and bool(session.get("guest_id"))


def get_chat_identity():
    """
    Return a private database identity for the current chat session.
    Registered users retain their existing email-based identity.
    Each guest receives a separate, random identity.
    """
    username = get_authenticated_username()
    if username:
        return username

    if is_guest_session():
        return f"guest_{session['guest_id']}"

    return None


def authentication_required():
    """Standard JSON response for unauthenticated API requests."""
    return jsonify({
        "success": False,
        "message": "Your session has expired. Please sign in or continue as a guest.",
        "error": "authentication_required",
        "redirect": "/login",
    }), 401


def guest_upload_forbidden():
    return jsonify({
        "success": False,
        "message": "Please create an account or sign in to upload documents.",
        "redirect": "/login",
    }), 403


def get_user_upload_dir(username):
    """Return the existing per-user upload directory."""
    safe_username = secure_filename(username)

    if not safe_username:
        raise ValueError("Invalid user identifier.")

    user_dir = UPLOAD_DIR / safe_username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_unique_filename(directory, filename):
    filename = secure_filename(filename)

    if not filename:
        raise ValueError("Please upload a file with a valid filename.")

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = filename
    counter = 2

    while (directory / candidate).exists():
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    return candidate


def save_chat(username, message, response, sources=None):
    conn = connect_db()

    try:
        conn.execute(
            """
            INSERT INTO chats
                (username, message, response, sources, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                message,
                response,
                json.dumps(sources or [], ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def build_sources(retrieved_chunks):
    """Build a deduplicated list of source passages."""
    sources = []
    seen = set()

    for chunk in retrieved_chunks:
        filename = chunk.get("filename", "Uploaded document")
        page = chunk.get("page")
        key = (filename, page)

        if key in seen:
            continue

        seen.add(key)

        sources.append({
            "filename": filename,
            "page": page,
            "score": round(float(chunk.get("score", 0)), 4),
            "excerpt": str(chunk.get("text", ""))[:350],
        })

    return sources


def read_saved_sources(value):
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def verify_and_upgrade_password(user, supplied_password, conn):
    """
    Verify a password hash and upgrade legacy plaintext passwords
    when an existing user successfully signs in.
    """
    stored_password = user["password"]

    try:
        if check_password_hash(stored_password, supplied_password):
            return True
    except (ValueError, TypeError):
        pass

    # Backward compatibility for legacy plaintext passwords.
    if stored_password == supplied_password:
        hashed_password = generate_password_hash(supplied_password)

        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (hashed_password, user["username"]),
        )
        conn.commit()
        return True

    return False


# --------------------------------------------------
# Main pages
# --------------------------------------------------

@app.route("/")
def home():
    if get_authenticated_username() or is_guest_session():
        return redirect(url_for("chat_page"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET"])
def login_page():
    if get_authenticated_username():
        return redirect(url_for("chat_page"))
    return render_template("login.html")


@app.route("/chat-page")
def chat_page():
    if not get_authenticated_username() and not is_guest_session():
        return redirect(url_for("login_page"))

    return render_template("chat.html")



# --------------------------------------------------
# Guest session
# --------------------------------------------------

@app.route("/guest", methods=["GET", "POST"])
def start_guest_session():
    """Start a limited guest session without creating a database account."""
    session.clear()
    session.permanent = True
    session["is_guest"] = True
    session["guest_id"] = secrets.token_urlsafe(18)
    session["guest_questions_used"] = 0

    # The login page uses POST and expects a JSON response.
    if request.method == "POST":
        return jsonify({
            "success": True,
            "message": "Guest session started successfully.",
            "is_guest": True,
            "username": "guest",
            "questions_used": 0,
            "questions_remaining": GUEST_QUESTION_LIMIT,
            "question_limit": GUEST_QUESTION_LIMIT,
            "redirect": url_for("chat_page"),
        }), 200

    # Keep GET support for compatibility with direct links.
    return redirect(url_for("chat_page"))



# --------------------------------------------------
# Registration
# --------------------------------------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or request.form

    email = normalize_email(data.get("email") or data.get("username"))
    full_name = str(data.get("full_name") or data.get("name") or "").strip()
    password = str(data.get("password") or "")

    if not full_name or len(full_name) < 2:
        return jsonify({
            "success": False,
            "message": "Please enter your full name (at least 2 characters).",
        }), 400

    if not valid_email(email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address.",
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters.",
        }), 400

    username = email
    password_hash = generate_password_hash(password)
    conn = connect_db()

    try:
        conn.execute(
            """
            INSERT INTO users (username, password, full_name)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, full_name),
        )
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Registration successful. Please sign in.",
            "username": username,
            "name": full_name,
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "message": "An account with this email already exists.",
        }), 409

    finally:
        conn.close()


# --------------------------------------------------
# Login and logout
# --------------------------------------------------

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form

    email = normalize_email(data.get("email") or data.get("username"))
    password = str(data.get("password") or "")

    if not valid_email(email):
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address.",
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters.",
        }), 400

    conn = connect_db()

    try:
        user = conn.execute(
            """
            SELECT username, password, full_name
            FROM users
            WHERE username = ?
            """,
            (email,),
        ).fetchone()

        if user and verify_and_upgrade_password(user, password, conn):
            display_name = (
                user["full_name"]
                if user["full_name"] and user["full_name"].strip()
                else email.split("@")[0]
            )

            # Clear guest or previous session before authenticating.
            session.clear()
            session.permanent = True
            session["username"] = user["username"]
            session["display_name"] = display_name

            return jsonify({
                "success": True,
                "message": "Login successful.",
                "username": user["username"],
                "name": display_name,
                "full_name": display_name,
            }), 200

        return jsonify({
            "success": False,
            "message": "Invalid email or password.",
        }), 401

    finally:
        conn.close()


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully.",
    }), 200


@app.route("/session", methods=["GET"])
def session_status():
    """Return current session details without exposing credentials."""
    username = get_authenticated_username()

    if username:
        return jsonify({
            "success": True,
            "is_guest": False,
            "username": username,
            "name": session.get("display_name") or username.split("@")[0],
        }), 200

    if is_guest_session():
        used = int(session.get("guest_questions_used", 0))
        used = max(0, min(used, GUEST_QUESTION_LIMIT))

        return jsonify({
            "success": True,
            "is_guest": True,
            "username": "guest",
            "name": "Guest",
            "display_name": "Guest",
            "questions_used": used,
            "questions_remaining": max(0, GUEST_QUESTION_LIMIT - used),
            "question_limit": GUEST_QUESTION_LIMIT,
        }), 200

    return authentication_required()


# --------------------------------------------------
# Persistent document upload
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload_document():
    # Guests cannot upload files or create persistent document records.
    if is_guest_session():
        return guest_upload_forbidden()

    # Never trust a username supplied in the upload form.
    username = get_authenticated_username()

    if not username:
        return authentication_required()

    uploaded_file = (
        request.files.get("file")
        or request.files.get("pdf")
        or request.files.get("document")
    )

    if uploaded_file is None or not uploaded_file.filename:
        return jsonify({
            "success": False,
            "message": "Please select a PDF or DOCX file.",
        }), 400

    if not allowed_file(uploaded_file.filename):
        return jsonify({
            "success": False,
            "message": "Unsupported file type. Upload a PDF or DOCX file.",
        }), 400

    original_filename = secure_filename(uploaded_file.filename)

    if not original_filename:
        return jsonify({
            "success": False,
            "message": "The uploaded filename is invalid.",
        }), 400

    extension = Path(original_filename).suffix.lower()
    user_dir = get_user_upload_dir(username)
    saved_filename = get_unique_filename(user_dir, original_filename)
    file_path = user_dir / saved_filename

    document_id = None
    document_inserted = False

    try:
        uploaded_file.save(str(file_path))
        pages = extract_document(str(file_path), saved_filename)

        if not pages or not any(
            isinstance(item, dict) and str(item.get("text", "")).strip()
            for item in pages
        ):
            file_path.unlink(missing_ok=True)

            return jsonify({
                "success": False,
                "message": (
                    "No readable text was found. "
                    "Scanned PDFs may require OCR."
                ),
            }), 422

        relative_path = file_path.relative_to(BASE_DIR).as_posix()
        conn = connect_db()

        try:
            cursor = conn.execute(
                """
                INSERT INTO documents
                    (username, filename, filepath, filetype)
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    saved_filename,
                    relative_path,
                    extension.lstrip("."),
                ),
            )

            document_id = cursor.lastrowid
            conn.commit()
            document_inserted = True

        finally:
            conn.close()

        chunk_count = save_document_chunks(document_id, pages)

        return jsonify({
            "success": True,
            "message": (
                f"{saved_filename} uploaded successfully. "
                "You can now ask questions about it."
            ),
            "filename": saved_filename,
            "filetype": extension.lstrip("."),
            "chunks": chunk_count,
        }), 200

    except Exception:
        app.logger.exception("Document upload failed")

        if document_inserted and document_id is not None:
            conn = connect_db()

            try:
                conn.execute(
                    "DELETE FROM documents WHERE id = ? AND username = ?",
                    (document_id, username),
                )
                conn.commit()
            except Exception:
                app.logger.exception("Could not clean up failed document record")
            finally:
                conn.close()

        file_path.unlink(missing_ok=True)

        return jsonify({
            "success": False,
            "message": (
                "Document processing failed. "
                "Check the Flask terminal for details."
            ),
        }), 500


# --------------------------------------------------
# List uploaded documents
# --------------------------------------------------

@app.route("/documents/<username>", methods=["GET"])
def list_documents(username):
    # Keep the existing URL shape for frontend compatibility.
    # Guests have no uploaded documents.
    if is_guest_session():
        return jsonify({"success": True, "documents": []}), 200

    authenticated_username = get_authenticated_username()

    if not authenticated_username:
        return authentication_required()

    conn = connect_db()

    try:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.filename,
                d.filetype,
                d.uploaded_at,
                COUNT(dc.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks dc
                ON dc.document_id = d.id
            WHERE d.username = ?
            GROUP BY d.id
            ORDER BY d.uploaded_at DESC, d.id DESC
            """,
            (authenticated_username,),
        ).fetchall()

        return jsonify({
            "success": True,
            "documents": [
                {
                    "id": row["id"],
                    "filename": row["filename"],
                    "filetype": row["filetype"],
                    "uploaded_at": row["uploaded_at"],
                    "chunks": row["chunk_count"],
                }
                for row in rows
            ],
        }), 200

    finally:
        conn.close()


# --------------------------------------------------
# Chat endpoint: general AI + document RAG
# --------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    # Registered user or isolated guest identity.
    username = get_chat_identity()

    if not username:
        return authentication_required()

    is_guest = is_guest_session()

    # Enforce the limit on the server, not just in JavaScript.
    if is_guest:
        questions_used = int(session.get("guest_questions_used", 0))

        if questions_used >= GUEST_QUESTION_LIMIT:
            return jsonify({
                "success": False,
                "response": (
                    "You've reached the 5-question guest limit. "
                    "Create an account or sign in to continue."
                ),
                "message": (
                    "You've reached the 5-question guest limit. "
                    "Create an account or sign in to continue."
                ),
                "limit_reached": True,
                "questions_used": questions_used,
                "questions_remaining": 0,
                "redirect": "/login",
                "confidence": 0.0,
                "sources": [],
            }), 403

    data = request.get_json(silent=True) or {}
    user_input = str(data.get("message") or "").strip()

    if not user_input:
        return jsonify({
            "success": False,
            "response": "Please enter a question.",
            "confidence": 0.0,
            "sources": [],
        }), 400

    try:
        document_question = _is_document_question(user_input)

        if not document_question:
            answer = generate_answer(user_input, [])
            sources = []
            confidence = 0.0

        else:
            # Guests have no private uploaded documents; search is scoped
            # to their unique guest identity and cannot expose user documents.
            retrieved_chunks = search(
                user_input,
                k=5,
                min_score=0.25,
                username=username,
            )

            if not retrieved_chunks:
                answer = generate_answer(user_input, [])
                sources = []
                confidence = 0.0

            else:
                answer = generate_answer(user_input, retrieved_chunks)
                sources = build_sources(retrieved_chunks)
                confidence = max(
                    float(chunk.get("score", 0))
                    for chunk in retrieved_chunks
                )

        # Only successful generated answers are stored and counted.
        save_chat(username, user_input, answer, sources)

        if is_guest:
            questions_used = int(session.get("guest_questions_used", 0)) + 1
            session["guest_questions_used"] = questions_used

            questions_remaining = max(
                0, GUEST_QUESTION_LIMIT - questions_used
            )
        else:
            questions_used = None
            questions_remaining = None

        return jsonify({
            "success": True,
            "response": answer,
            "confidence": round(confidence, 4),
            "sources": sources,
            "is_guest": is_guest,
            "questions_used": questions_used,
            "questions_remaining": questions_remaining,
            "question_limit": GUEST_QUESTION_LIMIT if is_guest else None,
        }), 200

    except Exception:
        app.logger.exception("Chat request failed")

        return jsonify({
            "success": False,
            "response": (
                "I couldn't process that question right now. "
                "Please check the Flask terminal for details."
            ),
            "confidence": 0.0,
            "sources": [],
        }), 500


# --------------------------------------------------
# Persistent chat history
# --------------------------------------------------

@app.route("/history/<username>", methods=["GET"])
def get_history(username):
    # Guest chat history is not mixed with registered user history.
    authenticated_username = get_authenticated_username()

    if is_guest_session():
        guest_identity = get_chat_identity()
        conn = connect_db()

        try:
            rows = conn.execute(
                """
                SELECT message, response, sources, created_at
                FROM chats
                WHERE username = ?
                ORDER BY id ASC
                """,
                (guest_identity,),
            ).fetchall()

            return jsonify({
                "success": True,
                "history": [
                    {
                        "message": row["message"],
                        "response": row["response"],
                        "sources": read_saved_sources(row["sources"]),
                        "created_at": row["created_at"],
                    }
                    for row in rows
                ],
            }), 200

        finally:
            conn.close()

    if not authenticated_username:
        return authentication_required()

    conn = connect_db()

    try:
        rows = conn.execute(
            """
            SELECT message, response, sources, created_at
            FROM chats
            WHERE username = ?
            ORDER BY id ASC
            """,
            (authenticated_username,),
        ).fetchall()

        history = [
            {
                "message": row["message"],
                "response": row["response"],
                "sources": read_saved_sources(row["sources"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

        return jsonify({
            "success": True,
            "history": history,
        }), 200

    finally:
        conn.close()


# --------------------------------------------------
# Error handling
# --------------------------------------------------

@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({
        "success": False,
        "message": "File is too large. The maximum upload size is 10 MB.",
    }), 413


# --------------------------------------------------
# Local development
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
    )

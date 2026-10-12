
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chatbot.db"


def connect_db():
    """Create a SQLite connection with named-column access."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    """Create application tables and migrate existing chat history."""
    conn = connect_db()

    try:
        cursor = conn.cursor()

        # Existing user accounts.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)

        # Existing conversations, with persistent source references.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                created_at TEXT
            )
        """)

        # Migrate existing databases without deleting chat records.
        cursor.execute("PRAGMA table_info(chats)")
        chat_columns = {
            row["name"] for row in cursor.fetchall()
        }

        if "sources" not in chat_columns:
            cursor.execute(
                "ALTER TABLE chats ADD COLUMN sources TEXT DEFAULT '[]'"
            )

        if "created_at" not in chat_columns:
            cursor.execute(
                "ALTER TABLE chats ADD COLUMN created_at TEXT"
            )

        # Metadata for files uploaded to the document library.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                filetype TEXT NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, filename)
            )
        """)

        # Extracted text chunks remain available after a restart.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                page INTEGER,
                text TEXT NOT NULL,
                FOREIGN KEY (document_id)
                    REFERENCES documents(id)
                    ON DELETE CASCADE,
                UNIQUE(document_id, chunk_index)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chats_username_id
            ON chats(username, id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_username
            ON documents(username)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_document
            ON document_chunks(document_id)
        """)

        conn.commit()

    finally:
        conn.close()

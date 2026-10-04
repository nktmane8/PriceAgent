"""SQLite storage: documents, chunks, an FTS5 keyword index (BM25) and optional embeddings."""
import hashlib
import json
import os
import sqlite3
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, title TEXT, url TEXT, source_type TEXT, product TEXT, country TEXT,
  published TEXT, added REAL, sha TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
  pos INTEGER, text TEXT NOT NULL, embedding TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text); END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text); END;
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, who TEXT, ts REAL);
"""


def connect() -> sqlite3.Connection:
    d = os.path.dirname(config.DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(SCHEMA)
    return c


def add_document(c, meta: dict, chunks: list[str], embeddings: list | None = None):
    """Insert a document and its chunks. Returns (doc_id, created). Same text twice = same document."""
    sha = hashlib.sha256("\n".join(chunks).encode()).hexdigest()
    row = c.execute("SELECT id FROM docs WHERE sha=?", (sha,)).fetchone()
    if row:
        return row["id"], False
    cur = c.execute("INSERT INTO docs(title,url,source_type,product,country,published,added,sha) VALUES(?,?,?,?,?,?,?,?)",
                    (meta.get("title", ""), meta.get("url", ""), meta.get("source_type", "other"), meta.get("product", ""),
                     meta.get("country", ""), meta.get("published", ""), time.time(), sha))
    for i, text in enumerate(chunks):
        emb = json.dumps(embeddings[i]) if embeddings else None
        c.execute("INSERT INTO chunks(doc_id,pos,text,embedding) VALUES(?,?,?,?)", (cur.lastrowid, i, text, emb))
    c.commit()
    return cur.lastrowid, True


def delete_document(c, doc_id: int) -> bool:
    n = c.execute("DELETE FROM docs WHERE id=?", (doc_id,)).rowcount
    c.commit()
    return n > 0


def list_documents(c):
    return [dict(r) for r in c.execute(
        "SELECT d.id,d.title,d.url,d.source_type,d.product,d.country,d.published,COUNT(k.id) chunks "
        "FROM docs d LEFT JOIN chunks k ON k.doc_id=d.id GROUP BY d.id ORDER BY d.id DESC LIMIT 500")]

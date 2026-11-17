import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    storage_key   TEXT NOT NULL UNIQUE,
    size          INTEGER NOT NULL,
    content_type  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    share_token   TEXT UNIQUE,
    share_expires TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id);
"""


def utcnow():
    return datetime.now(timezone.utc)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app):
    os.makedirs(os.path.dirname(os.path.abspath(app.config["DATABASE_PATH"])), exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        get_db().executescript(SCHEMA)

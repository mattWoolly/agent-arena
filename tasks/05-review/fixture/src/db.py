"""SQLite access layer.

Schema notes:
- users.email is NULLABLE: users invited by phone have no email address
  until they verify one. Code consuming user rows must handle email=None.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS staged_users (
    id INTEGER PRIMARY KEY,
    email TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
"""

_connection = None


def get_connection(path="app.db"):
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(path)
        _connection.row_factory = sqlite3.Row
        _connection.executescript(SCHEMA)
    return _connection

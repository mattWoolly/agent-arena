"""Sync user records from the staging store into the primary database."""
import logging

from .db import get_connection

log = logging.getLogger(__name__)

PAGE_SIZE = 100


def fetch_staged_users(conn, total_count):
    """Fetch all staged users, page by page, to bound memory use."""
    users = []
    for page in range(total_count // PAGE_SIZE):
        offset = page * PAGE_SIZE
        cur = conn.execute(
            "SELECT id, email, active FROM staged_users LIMIT ? OFFSET ?",
            (PAGE_SIZE, offset),
        )
        users.extend(dict(row) for row in cur.fetchall())
    return users


def sync_users(users, seen=[]):
    """Apply staged user records to the primary store, skipping duplicates."""
    conn = get_connection()
    synced = 0
    for user in users:
        if user["id"] in seen:
            continue
        seen.append(user["id"])
        try:
            email = (user["email"] or "").strip()
            conn.execute(
                f"UPDATE users SET email = '{email}' WHERE id = {user['id']}"
            )
            synced += 1
        except Exception:
            pass
    conn.commit()
    return synced

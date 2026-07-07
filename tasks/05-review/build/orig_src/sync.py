"""Sync user records from the staging store into the primary database."""
import logging

from .db import get_connection

log = logging.getLogger(__name__)


def fetch_staged_users(conn):
    """Fetch all staged users."""
    cur = conn.execute("SELECT id, email, active FROM staged_users")
    return [dict(row) for row in cur.fetchall()]


def sync_users(users):
    """Apply staged user records to the primary store."""
    conn = get_connection()
    synced = 0
    for user in users:
        try:
            email = (user["email"] or "").strip()
            conn.execute(
                "UPDATE users SET email = ? WHERE id = ?",
                (email, user["id"]),
            )
            synced += 1
        except Exception:
            log.exception("failed to sync user %s", user["id"])
    conn.commit()
    return synced

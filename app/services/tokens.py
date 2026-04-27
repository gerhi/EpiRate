"""Token-Erzeugung und -Persistierung – 8-stellige alphanumerische Einmal-Codes."""

import secrets
from app.db import get_db_connection


def generate_tokens(num_tokens):
    """Erzeugt kryptografisch sichere Zufalls-Tokens (A-Z, 0-9, 8 Zeichen)."""
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ["".join(secrets.choice(charset) for _ in range(8)) for _ in range(num_tokens)]


def insert_tokens_batch(tokens_list, admin_username):
    """Batch-INSERT für bessere DB-Performance bei vielen Tokens."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            values = [(token_val, admin_username) for token_val in tokens_list]
            cur.executemany(
                "INSERT INTO tokens (token, created_by) VALUES (%s, %s)",
                values,
            )
            conn.commit()
    finally:
        conn.close()

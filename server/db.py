"""SQLite-backed user accounts: password auth + ELO rating. The only place
in the codebase that knows about password hashing or the users table."""

import hashlib
import os
import sqlite3

DEFAULT_DB_PATH = "server/users.db"
STARTING_ELO = 1200
PBKDF2_ITERATIONS = 100_000


def init_db(path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            elo INTEGER NOT NULL DEFAULT {STARTING_ELO}
        )
        """
    )
    conn.commit()
    return conn


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS).hex()


def authenticate_or_register(conn: sqlite3.Connection, username: str, password: str) -> bool:
    """First login for a username creates the account; later logins must
    match the stored password. Returns whether the caller is now authenticated."""
    row = conn.execute(
        "SELECT password_hash, salt FROM users WHERE username = ?", (username,)
    ).fetchone()

    if row is None:
        salt = os.urandom(16)
        password_hash = _hash_password(password, salt)
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, elo) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt.hex(), STARTING_ELO),
        )
        conn.commit()
        return True

    stored_hash, salt_hex = row
    return _hash_password(password, bytes.fromhex(salt_hex)) == stored_hash


def get_elo(conn: sqlite3.Connection, username: str) -> int:
    row = conn.execute("SELECT elo FROM users WHERE username = ?", (username,)).fetchone()
    return row[0] if row else STARTING_ELO


def update_elo(conn: sqlite3.Connection, username: str, new_elo: int) -> None:
    conn.execute("UPDATE users SET elo = ? WHERE username = ?", (new_elo, username))
    conn.commit()

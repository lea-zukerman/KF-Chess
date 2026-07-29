"""User accounts: password auth + ELO rating. The only place in the
codebase that knows about password hashing or the users table.

Backed by PostgreSQL when given a postgresql:// url and by SQLite
otherwise, behind one set of functions. Both are real: PostgreSQL is what
the deployed server uses, SQLite keeps the test suite runnable without a
database process. Only the parameter placeholder differs between them --
see _placeholder.
"""

import hashlib
import os
import sqlite3

# Overridden per container by the DB_URL environment variable; the local
# file path is the fallback for running the server straight from a shell.
DEFAULT_DB_URL = os.environ.get("DB_URL", "server/users.db")
POSTGRES_URL_PREFIXES = ("postgresql://", "postgres://")
STARTING_ELO = 1200
PBKDF2_ITERATIONS = 100_000


def init_db(url: str = DEFAULT_DB_URL):
    """Connect and make sure the users table exists.

    `url` is a postgresql:// connection string, or any SQLite path
    (":memory:" included).
    """
    if url.startswith(POSTGRES_URL_PREFIXES):
        import psycopg  # only needed for the PostgreSQL path

        conn = psycopg.connect(url)
    else:
        conn = sqlite3.connect(url)

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


def _placeholder(conn) -> str:
    """SQLite spells query parameters '?', PostgreSQL spells them '%s'.

    The result is only ever one of those two literals -- values still go
    through the driver as parameters, never into the query text.
    """
    return "?" if isinstance(conn, sqlite3.Connection) else "%s"


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS).hex()


def authenticate_or_register(conn, username: str, password: str) -> bool:
    """First login for a username creates the account; later logins must
    match the stored password. Returns whether the caller is now authenticated."""
    p = _placeholder(conn)
    row = conn.execute(
        f"SELECT password_hash, salt FROM users WHERE username = {p}", (username,)
    ).fetchone()

    if row is None:
        salt = os.urandom(16)
        password_hash = _hash_password(password, salt)
        conn.execute(
            f"INSERT INTO users (username, password_hash, salt, elo)"
            f" VALUES ({p}, {p}, {p}, {p})",
            (username, password_hash, salt.hex(), STARTING_ELO),
        )
        conn.commit()
        return True

    stored_hash, salt_hex = row
    return _hash_password(password, bytes.fromhex(salt_hex)) == stored_hash


def get_elo(conn, username: str) -> int:
    p = _placeholder(conn)
    row = conn.execute(
        f"SELECT elo FROM users WHERE username = {p}", (username,)
    ).fetchone()
    return row[0] if row else STARTING_ELO


def update_elo(conn, username: str, new_elo: int) -> None:
    p = _placeholder(conn)
    conn.execute(
        f"UPDATE users SET elo = {p} WHERE username = {p}", (new_elo, username)
    )
    conn.commit()

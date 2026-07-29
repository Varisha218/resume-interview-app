"""Username/password auth backed by PostgreSQL.

Passwords are hashed with werkzeug's generate_password_hash (PBKDF2) —
plaintext is never stored. Sessions are handled by Flask's signed cookie
session (see app.py), so this module only deals with the users table.
"""

import re
import time

from psycopg2 import errors as pg_errors
from werkzeug.security import check_password_hash, generate_password_hash

from utils import db

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    pass


def signup(username: str, email: str, password: str) -> dict:
    username = (username or "").strip()
    email = (email or "").strip().lower()
    password = password or ""

    if not USERNAME_RE.match(username):
        raise AuthError("Username must be 3-32 characters (letters, numbers, _ . -).")
    if not EMAIL_RE.match(email):
        raise AuthError("Please enter a valid email address.")
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")

    password_hash = generate_password_hash(password)

    try:
        with db.get_cursor() as cur:
            cur.execute(
                """INSERT INTO users (username, email, password_hash, created_at)
                   VALUES (%s, %s, %s, %s) RETURNING id, username, email, created_at""",
                (username, email, password_hash, time.time()),
            )
            row = cur.fetchone()
    except pg_errors.UniqueViolation:
        raise AuthError("That username or email is already taken.")

    return dict(row)


def login(username_or_email: str, password: str) -> dict:
    identifier = (username_or_email or "").strip().lower()
    if not identifier or not password:
        raise AuthError("Enter your username/email and password.")

    with db.get_cursor() as cur:
        cur.execute(
            """SELECT id, username, email, password_hash, created_at FROM users
               WHERE lower(username) = %s OR lower(email) = %s""",
            (identifier, identifier),
        )
        row = cur.fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        raise AuthError("Incorrect username/email or password.")

    return {"id": row["id"], "username": row["username"], "email": row["email"], "created_at": row["created_at"]}


def get_user(user_id: int) -> dict | None:
    with db.get_cursor() as cur:
        cur.execute("SELECT id, username, email, created_at FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return dict(row) if row else None

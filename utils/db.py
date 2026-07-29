"""PostgreSQL connection layer.

Reads connection info from the DATABASE_URL environment variable, e.g.

    postgresql://user:password@localhost:5432/interview_coach

Falls back to the individual PG* environment variables (PGHOST, PGPORT,
PGDATABASE, PGUSER, PGPASSWORD) if DATABASE_URL isn't set, which is handy
in docker-compose setups.
"""

import os
import time
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get(
    "POSTGRES_URL",
    "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        db=os.environ.get("PGDATABASE", "interview_coach"),
    ),
)

MIN_POOL_CONNS = int(os.environ.get("DB_POOL_MIN", "1"))
MAX_POOL_CONNS = int(os.environ.get("DB_POOL_MAX", "10"))

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            MIN_POOL_CONNS, MAX_POOL_CONNS, DATABASE_URL
        )
    return _pool


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(dict_cursor=True):
    with get_conn() as conn:
        cursor_factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    overall_score DOUBLE PRECISION NOT NULL,
    relevance_score DOUBLE PRECISION,
    structure_score DOUBLE PRECISION,
    fluency_score DOUBLE PRECISION,
    highest_difficulty_reached TEXT,
    question_count INTEGER,
    recommendations TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    practiced_date DATE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON interview_sessions(user_id);

CREATE TABLE IF NOT EXISTS streaks (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_practice_date DATE
);

CREATE TABLE IF NOT EXISTS medals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT NOT NULL,
    awarded_at DOUBLE PRECISION NOT NULL,
    UNIQUE(user_id, code)
);
"""


def init_db(retries: int = 5, delay: float = 1.5):
    """Creates the schema if it doesn't exist yet. Retries on connection
    errors so the app can start up right after `docker compose up` even
    if Postgres hasn't finished booting yet."""
    last_err = None
    for attempt in range(retries):
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(SCHEMA)
                cur.close()
            return
        except psycopg2.OperationalError as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(
        f"Could not connect to PostgreSQL after {retries} attempts: {last_err}"
    )

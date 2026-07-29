"""Streaks and medals for practice/mock interviews.

Streak = consecutive calendar days with at least one finished interview
session (practice or mock). Medals are awarded once, permanently, the
first time their condition becomes true.
"""

import datetime
import time

from utils import db

MEDAL_CATALOG = [
    {"code": "first_session", "label": "First Steps", "icon": "🎯",
     "desc": "Complete your first interview session."},
    {"code": "five_sessions", "label": "Warming Up", "icon": "🔥",
     "desc": "Complete 5 interview sessions."},
    {"code": "twenty_sessions", "label": "Dedicated", "icon": "💪",
     "desc": "Complete 20 interview sessions."},
    {"code": "streak_3", "label": "Consistency", "icon": "🔥",
     "desc": "Practice 3 days in a row."},
    {"code": "streak_7", "label": "On Fire", "icon": "🔥🔥",
     "desc": "Practice 7 days in a row."},
    {"code": "streak_30", "label": "Unstoppable", "icon": "🏆",
     "desc": "Practice 30 days in a row."},
    {"code": "first_mock", "label": "Mock Ready", "icon": "🎤",
     "desc": "Complete your first mock interview."},
    {"code": "score_85", "label": "Sharp Shooter", "icon": "🥇",
     "desc": "Score 85% or higher on a session."},
    {"code": "score_95", "label": "Perfectionist", "icon": "💎",
     "desc": "Score 95% or higher on a session."},
    {"code": "hard_difficulty", "label": "Deep End", "icon": "🧠",
     "desc": "Reach hard-difficulty questions in a mock interview."},
]
MEDAL_BY_CODE = {m["code"]: m for m in MEDAL_CATALOG}


def _today():
    return datetime.date.today()


def update_streak(user_id: int, practiced_date: datetime.date) -> dict:
    """Updates the streak row for a finished session and returns the new
    streak state: {current_streak, longest_streak}."""
    with db.get_cursor() as cur:
        cur.execute("SELECT current_streak, longest_streak, last_practice_date "
                     "FROM streaks WHERE user_id = %s", (user_id,))
        row = cur.fetchone()

        if row is None:
            current_streak, longest_streak, last_date = 0, 0, None
        else:
            current_streak = row["current_streak"]
            longest_streak = row["longest_streak"]
            last_date = row["last_practice_date"]

        if last_date == practiced_date:
            pass  # already practiced today, streak unchanged
        elif last_date == practiced_date - datetime.timedelta(days=1):
            current_streak += 1
        else:
            current_streak = 1

        longest_streak = max(longest_streak, current_streak)

        cur.execute(
            """INSERT INTO streaks (user_id, current_streak, longest_streak, last_practice_date)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                 current_streak = EXCLUDED.current_streak,
                 longest_streak = EXCLUDED.longest_streak,
                 last_practice_date = EXCLUDED.last_practice_date""",
            (user_id, current_streak, longest_streak, practiced_date),
        )

    return {"current_streak": current_streak, "longest_streak": longest_streak}


def get_streak(user_id: int) -> dict:
    with db.get_cursor() as cur:
        cur.execute("SELECT current_streak, longest_streak, last_practice_date "
                     "FROM streaks WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    if not row:
        return {"current_streak": 0, "longest_streak": 0}

    # A day missed since last login silently lapses the *current* streak
    # display (longest_streak is untouched; DB updates lazily on next session).
    current = row["current_streak"]
    if row["last_practice_date"] and row["last_practice_date"] < _today() - datetime.timedelta(days=1):
        current = 0
    return {"current_streak": current, "longest_streak": row["longest_streak"]}


def get_medals(user_id: int) -> list:
    with db.get_cursor() as cur:
        cur.execute("SELECT code, label, icon, awarded_at FROM medals WHERE user_id = %s "
                     "ORDER BY awarded_at ASC", (user_id,))
        rows = [dict(r) for r in cur.fetchall()]
    owned_codes = {r["code"] for r in rows}
    locked = [m for m in MEDAL_CATALOG if m["code"] not in owned_codes]
    return {"earned": rows, "locked": locked}


def _award(user_id: int, code: str) -> bool:
    """Inserts a medal if not already owned. Returns True if newly awarded."""
    meta = MEDAL_BY_CODE[code]
    with db.get_cursor() as cur:
        cur.execute(
            """INSERT INTO medals (user_id, code, label, icon, awarded_at)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (user_id, code) DO NOTHING
               RETURNING id""",
            (user_id, code, meta["label"], meta["icon"], time.time()),
        )
        return cur.fetchone() is not None


def evaluate_medals(user_id: int, mode: str, overall_score: float,
                     highest_difficulty: str, streak_state: dict) -> list:
    """Call after a session is saved. Returns list of newly-earned medal dicts."""
    with db.get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM interview_sessions WHERE user_id = %s", (user_id,))
        session_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM interview_sessions WHERE user_id = %s AND mode = 'mock'",
                     (user_id,))
        mock_count = cur.fetchone()["c"]

    newly_awarded = []

    def maybe(code, condition):
        if condition and _award(user_id, code):
            newly_awarded.append(MEDAL_BY_CODE[code])

    maybe("first_session", session_count >= 1)
    maybe("five_sessions", session_count >= 5)
    maybe("twenty_sessions", session_count >= 20)
    maybe("streak_3", streak_state["current_streak"] >= 3)
    maybe("streak_7", streak_state["current_streak"] >= 7)
    maybe("streak_30", streak_state["current_streak"] >= 30)
    maybe("first_mock", mode == "mock" and mock_count >= 1)
    maybe("score_85", overall_score >= 85)
    maybe("score_95", overall_score >= 95)
    maybe("hard_difficulty", mode == "mock" and highest_difficulty == "hard")

    return newly_awarded

"""Persistence for interview session history, now backed by PostgreSQL and
keyed by the authenticated user's id (see utils/auth.py, utils/db.py)."""

import datetime
import json
import time

from utils import db


def save_session(user_id: int, mode: str, score_breakdown: dict,
                  highest_difficulty_reached: str, question_count: int,
                  recommendations: list, practiced_date: datetime.date = None) -> int:
    practiced_date = practiced_date or datetime.date.today()
    with db.get_cursor() as cur:
        cur.execute(
            """INSERT INTO interview_sessions
               (user_id, mode, overall_score, relevance_score, structure_score,
                fluency_score, highest_difficulty_reached, question_count,
                recommendations, created_at, practiced_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                user_id, mode,
                score_breakdown.get("overall", 0.0),
                score_breakdown.get("relevance", 0.0),
                score_breakdown.get("structure", 0.0),
                score_breakdown.get("fluency", 0.0),
                highest_difficulty_reached,
                question_count,
                json.dumps(recommendations or []),
                time.time(),
                practiced_date,
            ),
        )
        return cur.fetchone()["id"]


def get_history(user_id: int, limit: int = 10) -> list:
    if not user_id:
        return []
    with db.get_cursor() as cur:
        cur.execute(
            """SELECT mode, overall_score, relevance_score, structure_score,
                      fluency_score, highest_difficulty_reached, question_count,
                      created_at
               FROM interview_sessions WHERE user_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]

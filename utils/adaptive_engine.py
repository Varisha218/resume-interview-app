"""Adaptive Interview Engine.

Implements the scope document's requirement that the Mock Interview mode
"dynamically adjusts question difficulty according to candidate
performance." Difficulty moves up or down each turn based on the score of
the answer just given — nothing about the *sequence* of difficulties is
predetermined; it's a live function of performance.

Practice mode intentionally does NOT use this — it's meant for repeated,
lower-pressure training, so it walks the pool in a fixed, generous order
instead (see `next_question_practice`).
"""

TIERS = ["easy", "medium", "hard"]

ESCALATE_THRESHOLD = 72.0
DEESCALATE_THRESHOLD = 40.0


def next_difficulty(current_difficulty: str, last_score: float) -> str:
    """Given the difficulty just answered and its score (0-100), decide the
    difficulty of the next question.
    """
    idx = TIERS.index(current_difficulty) if current_difficulty in TIERS else 1

    if last_score >= ESCALATE_THRESHOLD:
        idx = min(len(TIERS) - 1, idx + 1)
    elif last_score < DEESCALATE_THRESHOLD:
        idx = max(0, idx - 1)
    # else: stay at the same tier

    return TIERS[idx]


def _pick_from_tier(pool: dict, asked_ids: set, tier: str):
    for q in pool.get(tier, []):
        if q.get("_id") not in asked_ids:
            return q
    return None


def next_question_adaptive(pool: dict, asked_ids: set, current_difficulty: str,
                            last_score: float = None) -> dict:
    """Mock-mode question selection: pick the next difficulty tier from live
    performance, then pull an unused question from that tier — falling back
    to neighboring tiers if the preferred one is exhausted.

    Returns {"question": <dict or None>, "difficulty": <str>}.
    """
    target = next_difficulty(current_difficulty, last_score) if last_score is not None else current_difficulty

    search_order = [target] + [t for t in TIERS if t != target]
    for tier in search_order:
        q = _pick_from_tier(pool, asked_ids, tier)
        if q:
            return {"question": q, "difficulty": tier}

    return {"question": None, "difficulty": target}


def next_question_practice(pool: dict, asked_ids: set) -> dict:
    """Practice-mode question selection: walk medium -> easy -> hard so the
    candidate warms up before harder prompts, without adapting to score
    (practice is meant to be repeatable, low-pressure training).
    """
    for tier in ["medium", "easy", "hard"]:
        q = _pick_from_tier(pool, asked_ids, tier)
        if q:
            return {"question": q, "difficulty": tier}
    return {"question": None, "difficulty": "medium"}

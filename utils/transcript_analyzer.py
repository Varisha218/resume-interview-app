"""Server-side speech/transcript evaluation for interview answers.

Replaces the old client-only scoring (plain substring keyword matching)
with a multi-signal pipeline:

1. Relevance  – semantic similarity (local SBERT model, same one used by
   the resume matcher) between the transcript and the question's "concept",
   blended with dynamic keyword coverage, so scoring isn't purely a fixed
   word list.
2. Fluency    – speaking pace vs. a natural conversational range, plus
   filler-word ratio (relative to the length of the answer, not an
   absolute count, so short and long answers are judged fairly).
3. Structure  – whether the answer actually has substance: multiple
   sentences, concrete action language, and (where relevant) a quantified
   result — reusing the same "does this look like a real, evidenced
   answer" signals the resume matcher already uses.

All three are combined into a single 0-100 communication_score, and a
short, data-driven feedback tip is generated from whichever sub-score is
weakest for *this* answer (no fixed canned tip list disconnected from the
actual numbers).
"""

import re

from . import semantic_model

# A closed set of English discourse fillers, used the same way the
# semantic_model module already uses a stopword list — not a business rule
# to tune per-project, just a fixed linguistic category.
FILLER_WORDS = ["um", "uh", "uhh", "umm", "like", "you know", "actually",
                "basically", "so yeah", "i mean", "kind of", "sort of"]

ACTION_VERBS = [
    "developed", "designed", "built", "led", "managed", "created", "implemented",
    "improved", "increased", "decreased", "reduced", "optimized", "launched",
    "coordinated", "analyzed", "automated", "delivered", "achieved", "engineered",
    "spearheaded", "streamlined", "accelerated", "initiated", "established",
    "resolved", "debugged", "tested", "collaborated", "researched",
]

IDEAL_WPM_LOW = 110
IDEAL_WPM_HIGH = 165


def _keyword_coverage(transcript_lower: str, keywords: list) -> float:
    if not keywords:
        return 0.0
    hits = sum(1 for k in keywords if k.lower() in transcript_lower)
    return hits / len(keywords)


def _relevance_score(transcript: str, concept: str, keywords: list) -> tuple:
    """Blend embedding similarity with keyword coverage.

    Falls back gracefully to keyword coverage alone if the embedding model
    can't be loaded (mirrors utils/semantic_model.py's own fallback logic).
    """
    transcript_lower = transcript.lower()
    coverage = _keyword_coverage(transcript_lower, keywords)

    if not transcript.strip():
        return 0.0, coverage, []

    sims = semantic_model.similarity_matrix([concept], [transcript])
    raw = float(sims[0][0]) if sims.size else 0.0
    # Same calibration bounds as document_similarity's real-model case —
    # a short concept phrase vs. a spoken paragraph behaves similarly to
    # comparing two differently-phrased documents.
    semantic = semantic_model._calibrate(raw, semantic_model._REAL_MODEL_FLOOR,
                                          semantic_model._REAL_MODEL_CEILING)

    hits = [k for k in keywords if k.lower() in transcript_lower]
    blended = 0.6 * semantic + 0.4 * coverage
    return blended, semantic, hits


def _fluency_score(word_count: int, duration_seconds: float, filler_count: int) -> float:
    if word_count == 0 or duration_seconds <= 0:
        return 0.0

    wpm = (word_count / duration_seconds) * 60
    if wpm < IDEAL_WPM_LOW:
        pace_score = max(0.0, wpm / IDEAL_WPM_LOW)
    elif wpm > IDEAL_WPM_HIGH:
        # Gentle falloff for talking fast rather than a hard cliff.
        pace_score = max(0.3, 1.0 - (wpm - IDEAL_WPM_HIGH) / (IDEAL_WPM_HIGH * 1.5))
    else:
        pace_score = 1.0

    filler_ratio = filler_count / max(1, word_count)
    filler_score = max(0.0, 1.0 - filler_ratio * 8)  # ~12.5% filler density zeroes this out

    return max(0.0, min(1.0, 0.6 * pace_score + 0.4 * filler_score))


def _structure_score(transcript: str) -> float:
    if not transcript.strip():
        return 0.0

    sentences = [s for s in re.split(r"[.!?]+", transcript) if s.strip()]
    sentence_score = min(1.0, len(sentences) / 3.0)  # 3+ sentences = a fleshed-out answer

    lower = transcript.lower()
    has_action_verb = any(re.search(r"(?<![a-z])" + v + r"(?![a-z])", lower) for v in ACTION_VERBS)
    has_metric = bool(re.search(r"\d+%|\$\d+|\b\d{2,}\b", transcript))

    score = 0.4 * sentence_score + 0.3 * (1.0 if has_action_verb else 0.0) + 0.3 * (1.0 if has_metric else 0.0)
    return max(0.0, min(1.0, score))


def _count_filler_words(transcript: str) -> int:
    lower = f" {transcript.lower()} "
    count = 0
    for w in FILLER_WORDS:
        pattern = r"\b" + re.escape(w) + r"\b"
        count += len(re.findall(pattern, lower))
    return count


def aggregate_session_score(evaluations: list) -> dict:
    """Average the per-answer evaluations into a session-level breakdown."""
    n = len(evaluations)
    if n == 0:
        return {"overall": 0.0, "relevance": 0.0, "structure": 0.0, "fluency": 0.0}

    def avg(key):
        return round(sum(e.get(key, 0.0) for e in evaluations) / n, 1)

    return {
        "overall": avg("overall"),
        "relevance": avg("relevance"),
        "structure": avg("structure"),
        "fluency": avg("fluency"),
    }


def build_recommendations(evaluations: list, questions: list) -> list:
    """Generate personalized recommendations/learning suggestions from the
    weakest sub-scores actually observed this session, referencing the
    specific missing concepts rather than generic advice.
    """
    n = len(evaluations)
    if n == 0:
        return ["No answers were recorded this session — try a full run to get personalized recommendations."]

    breakdown = aggregate_session_score(evaluations)
    recs = []

    all_missing = []
    for e in evaluations:
        all_missing.extend(e.get("missing_keywords", []))
    top_missing = [w for w in dict.fromkeys(all_missing)][:5]  # dedupe, keep order

    if breakdown["relevance"] < 55:
        hint = f" Focus especially on concepts like: {', '.join(top_missing)}." if top_missing else ""
        recs.append(
            f"<strong>Sharpen answer relevance</strong> (avg {breakdown['relevance']}%): "
            f"several answers drifted from what was actually asked.{hint}"
        )
    if breakdown["structure"] < 55:
        recs.append(
            f"<strong>Add more structure and evidence</strong> (avg {breakdown['structure']}%): "
            "use a situation → action → result shape, and back claims with a concrete "
            "example or number where possible."
        )
    if breakdown["fluency"] < 55:
        total_fillers = sum(e.get("filler_count", 0) for e in evaluations)
        recs.append(
            f"<strong>Work on delivery</strong> (avg {breakdown['fluency']}%): "
            f"{total_fillers} filler word(s) used across the session — practising "
            "answers out loud beforehand usually cuts this down quickly."
        )

    hardest_answered = [q.get("difficulty") for q in questions if q.get("difficulty") == "hard"]
    if not hardest_answered and n >= 4:
        recs.append(
            "<strong>Push for harder follow-ups</strong>: this session stayed mostly at "
            "easier/medium difficulty. Try a Mock Interview run and aim for stronger, more "
            "detailed answers early on to unlock harder questions."
        )

    if not recs:
        recs.append("Strong session overall — relevance, structure, and delivery were all solid.")

    return recs


def evaluate_answer(transcript: str, question: dict, duration_seconds: float) -> dict:
    """Evaluate a single answer against its question.

    `question` should contain: expected_keywords (list), concept (str),
    difficulty (str).
    """
    transcript = (transcript or "").strip()
    keywords = question.get("expected_keywords", [])
    concept = question.get("concept") or question.get("question", "")

    word_count = len(transcript.split()) if transcript else 0
    filler_count = _count_filler_words(transcript)
    wpm = round((word_count / duration_seconds) * 60) if duration_seconds > 0 and word_count else 0

    relevance_blended, relevance_semantic, keyword_hits = _relevance_score(transcript, concept, keywords)
    fluency = _fluency_score(word_count, duration_seconds, filler_count)
    structure = _structure_score(transcript)

    # Content (relevance + structure) dominates the score; fluency is
    # capped at a modest 20% weight — see utils/fairness.py for why this
    # weighting choice is a deliberate fairness safeguard, not just a
    # scoring preference.
    overall = round((0.55 * relevance_blended + 0.25 * structure + 0.20 * fluency) * 100, 1)
    overall = max(0.0, min(100.0, overall))

    missing_keywords = [k for k in keywords if k not in keyword_hits]

    if not transcript or word_count < 3:
        tip = "No meaningful speech was captured — try to speak clearly and give a complete answer."
    elif relevance_blended < 0.35:
        tip = f"Try to speak more directly to the question — consider mentioning: {', '.join(missing_keywords[:4]) or 'more specific detail'}."
    elif structure < 0.4:
        tip = "Good relevance, but the answer is thin — add a concrete example, a specific action you took, and a result or outcome."
    elif fluency < 0.5:
        tip = f"Solid content — work on pacing/filler words (used {filler_count} filler word(s)) for a smoother delivery."
    else:
        tip = "Strong answer — relevant, well-structured, and clearly delivered."

    return {
        "overall": overall,
        "relevance": round(relevance_blended * 100, 1),
        "structure": round(structure * 100, 1),
        "fluency": round(fluency * 100, 1),
        "word_count": word_count,
        "wpm": wpm,
        "filler_count": filler_count,
        "keyword_hits": keyword_hits,
        "missing_keywords": missing_keywords,
        "tip": tip,
    }

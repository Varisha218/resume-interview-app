"""AI fairness and bias-awareness mechanisms for interview evaluation.

The scope document requires "fairness and bias-awareness mechanisms... to
promote objective and balanced candidate evaluation." Concretely, this
module enforces and reports on one core policy:

  Webcam-derived signals (facial expression / "engagement", eye-contact
  proxy from face-detection ratio) are NEVER used as part of the numeric
  score. They're shown to the candidate purely as descriptive feedback.
  Scoring appearance/expression is a well-documented source of disparate
  impact in AI interview tools (it penalizes camera/lighting problems,
  neurodivergent presentation, cultural differences in expressiveness,
  etc.), so this system structurally excludes it from scoring rather than
  just down-weighting it.

The report is generated from the *actual session's* numbers, not static
boilerplate, so it stays meaningful across different candidates/sessions.
"""


def build_fairness_report(answers: list) -> dict:
    """Build a transparency report over a finished interview session.

    `answers` is a list of dicts, each expected to contain (best-effort,
    missing keys are treated as 0/empty):
      evaluation: {overall, relevance, structure, fluency}
      face_detect_ratio: float 0-1
      emotion_counts: dict
      skip_reason: str
    """
    n = len(answers)
    notes = []

    if n == 0:
        return {
            "scoring_inputs": ["relevance", "structure", "fluency"],
            "excluded_from_scoring": ["facial_expression", "eye_contact_proxy"],
            "notes": ["No answers were recorded, so no fairness signals could be computed."],
        }

    face_ratios = [a.get("face_detect_ratio", 0.0) for a in answers]
    avg_face_ratio = sum(face_ratios) / n

    filler_counts = [a.get("evaluation", {}).get("filler_count", 0) for a in answers]
    fluency_scores = [a.get("evaluation", {}).get("fluency", 0.0) for a in answers]
    avg_fluency = sum(fluency_scores) / n

    silence_skips = sum(1 for a in answers if a.get("skip_reason") == "silence")
    timeouts = sum(1 for a in answers if a.get("skip_reason") == "timeout")

    notes.append(
        "The overall score is computed only from what you said (relevance and "
        "structure of your answers) and how it was delivered (pace/filler "
        "words). Facial expression and eye-contact/camera-presence data shown "
        "on the summary screen are informational only and carry zero weight "
        "in your score, to avoid penalizing appearance, camera quality, "
        "lighting, or expressiveness differences that have nothing to do with "
        "answer quality."
    )

    if avg_face_ratio < 0.4:
        notes.append(
            f"Your face was reliably detected in only about {round(avg_face_ratio * 100)}% of "
            "sampled frames (likely lighting, camera angle, or webcam quality). "
            "This does not affect your score — it's flagged here only so a "
            "low engagement-looking number isn't misread as low participation."
        )

    if avg_fluency < 45:
        notes.append(
            "Speaking pace and filler-word density were on the rougher side this "
            "session. Fluency is intentionally capped at 20% of the overall "
            "score (relevance and structure make up the other 80%), since pace "
            "and filler-word rate can vary for reasons unrelated to competence "
            "(e.g. speaking in a non-native language, nervousness, or "
            "unfamiliarity with the mic setup)."
        )

    if silence_skips or timeouts:
        notes.append(
            f"{silence_skips} question(s) were auto-skipped due to silence and "
            f"{timeouts} timed out. These were scored on whatever partial "
            "transcript existed rather than treated as automatic failures, so a "
            "connectivity or nerves-related pause isn't conflated with not "
            "knowing the answer."
        )

    return {
        "scoring_inputs": ["relevance", "structure", "fluency"],
        "excluded_from_scoring": ["facial_expression", "eye_contact_proxy"],
        "avg_face_detect_ratio": round(avg_face_ratio, 3),
        "avg_fluency_score": round(avg_fluency, 1),
        "notes": notes,
    }

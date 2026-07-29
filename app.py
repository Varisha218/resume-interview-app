import datetime
import functools
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, jsonify, render_template, session

from utils.resume_parser import parse_resume
from utils.matcher import analyze_resume_vs_jd, compute_skill_weights
from utils.question_bank import generate_questions, generate_question_pool
from utils import adaptive_engine, transcript_analyzer, fairness, interview_store
from utils import db, auth, gamification
from utils.auth import AuthError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
# Used to sign the session cookie. Set SECRET_KEY in the environment for
# production so sessions survive app restarts / multiple workers.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")

db.init_db()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in to continue."}), 401
        return view(*args, **kwargs)
    return wrapped


def _profile_payload(user_id: int) -> dict:
    streak = gamification.get_streak(user_id)
    medals = gamification.get_medals(user_id)
    history = interview_store.get_history(user_id, limit=10)
    return {"streak": streak, "medals": medals, "history": history}


@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(force=True, silent=True) or {}
    try:
        user = auth.signup(data.get("username"), data.get("email"), data.get("password"))
    except AuthError as e:
        return jsonify({"error": str(e)}), 400

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": {"id": user["id"], "username": user["username"]},
                     "profile": _profile_payload(user["id"])})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    try:
        user = auth.login(data.get("username"), data.get("password"))
    except AuthError as e:
        return jsonify({"error": str(e)}), 400

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": {"id": user["id"], "username": user["username"]},
                     "profile": _profile_payload(user["id"])})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None}), 200
    user = auth.get_user(user_id)
    if not user:
        session.clear()
        return jsonify({"user": None}), 200
    return jsonify({"user": {"id": user["id"], "username": user["username"]},
                     "profile": _profile_payload(user_id)})


@app.route("/api/profile", methods=["GET"])
@login_required
def profile():
    return jsonify(_profile_payload(session["user_id"]))


# ---------------------------------------------------------------------
# Resume / JD analysis (unauthenticated -- only the interview + history
# steps require an account)
# ---------------------------------------------------------------------

@app.route("/api/upload_resume", methods=["POST"])
def upload_resume():
    if "resume" not in request.files:
        return jsonify({"error": "No resume file uploaded."}), 400

    file = request.files["resume"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Unsupported file type. Please upload PDF, DOCX, or TXT."}), 400

    temp_name = f"{uuid.uuid4().hex}{ext}"
    temp_path = os.path.join(UPLOAD_DIR, temp_name)
    file.save(temp_path)

    try:
        resume_text = parse_resume(temp_path)
        if not resume_text or len(resume_text.strip()) < 20:
            return jsonify({"error": "Could not extract meaningful text from this file. "
                                      "Try a different format or paste your resume text manually."}), 400
        return jsonify({"resume_text": resume_text})
    except Exception as e:
        return jsonify({"error": f"Failed to parse resume: {str(e)}"}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True, silent=True) or {}
    resume_text = (data.get("resume_text") or "").strip()
    jd_text = (data.get("jd_text") or "").strip()

    if not resume_text or not jd_text:
        return jsonify({"error": "Both resume text and job description are required."}), 400

    result = analyze_resume_vs_jd(resume_text, jd_text)
    return jsonify(result)


@app.route("/api/questions", methods=["POST"])
def questions():
    data = request.get_json(force=True, silent=True) or {}
    matched_skills = data.get("matched_skills") or []
    missing_skills = data.get("missing_skills") or []
    mode = data.get("mode") or "practice"
    count = int(data.get("count") or 6)
    resume_text = (data.get("resume_text") or "").strip()

    qs = generate_questions(matched_skills, missing_skills, mode=mode, count=count,
                            resume_text=resume_text)
    return jsonify({"questions": qs})


# ---------------------------------------------------------------------
# Interview flow (requires login -- sessions are tied to the account so
# streaks/medals/history can be tracked)
# ---------------------------------------------------------------------

@app.route("/api/interview/start", methods=["POST"])
@login_required
def interview_start():
    data = request.get_json(force=True, silent=True) or {}
    matched_skills = data.get("matched_skills") or []
    missing_skills = data.get("missing_skills") or []
    resume_text = (data.get("resume_text") or "").strip()
    jd_text = (data.get("jd_text") or "").strip()
    mode = data.get("mode") or "practice"

    skill_weights = compute_skill_weights(jd_text, list(matched_skills) + list(missing_skills))
    pool = generate_question_pool(matched_skills, missing_skills, resume_text, skill_weights)

    if not any(pool.values()):
        return jsonify({"error": "Could not generate any interview questions from this resume/JD."}), 400

    start_difficulty = "medium"
    if mode == "mock":
        picked = adaptive_engine.next_question_adaptive(pool, set(), start_difficulty)
    else:
        picked = adaptive_engine.next_question_practice(pool, set())

    question = picked["question"]
    asked_ids = [question["_id"]] if question else []

    return jsonify({
        "pool": pool,
        "question": question,
        "difficulty": picked["difficulty"],
        "asked_ids": asked_ids,
        "mode": mode,
    })


@app.route("/api/interview/next", methods=["POST"])
@login_required
def interview_next():
    data = request.get_json(force=True, silent=True) or {}
    pool = data.get("pool") or {}
    mode = data.get("mode") or "practice"
    asked_ids = set(data.get("asked_ids") or [])
    current_difficulty = data.get("current_difficulty") or "medium"
    last_question = data.get("last_question") or {}
    transcript = data.get("transcript") or ""
    duration_seconds = float(data.get("duration_seconds") or 1.0)
    max_questions = int(data.get("max_questions") or 6)

    evaluation = transcript_analyzer.evaluate_answer(transcript, last_question, duration_seconds)

    done = len(asked_ids) >= max_questions
    next_question = None
    next_difficulty = current_difficulty

    if not done:
        if mode == "mock":
            picked = adaptive_engine.next_question_adaptive(
                pool, asked_ids, current_difficulty, last_score=evaluation["overall"]
            )
        else:
            picked = adaptive_engine.next_question_practice(pool, asked_ids)

        next_question = picked["question"]
        next_difficulty = picked["difficulty"]
        if next_question:
            asked_ids.add(next_question["_id"])
        else:
            done = True

    return jsonify({
        "evaluation": evaluation,
        "next_question": next_question,
        "difficulty": next_difficulty,
        "asked_ids": list(asked_ids),
        "done": done,
    })


@app.route("/api/interview/finish", methods=["POST"])
@login_required
def interview_finish():
    user_id = session["user_id"]
    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode") or "practice"
    answers = data.get("answers") or []  # each: evaluation, face_detect_ratio, emotion_counts, skip_reason, difficulty

    evaluations = [a.get("evaluation", {}) for a in answers]
    score_breakdown = transcript_analyzer.aggregate_session_score(evaluations)
    recommendations = transcript_analyzer.build_recommendations(evaluations, answers)
    fairness_report = fairness.build_fairness_report(answers)

    difficulty_rank = {"easy": 0, "medium": 1, "hard": 2}
    reached = [a.get("difficulty", "easy") for a in answers]
    highest_difficulty = max(reached, key=lambda d: difficulty_rank.get(d, 0)) if reached else "easy"

    today = datetime.date.today()
    interview_store.save_session(
        user_id, mode, score_breakdown, highest_difficulty, len(answers), recommendations, today
    )
    streak_state = gamification.update_streak(user_id, today)
    newly_awarded = gamification.evaluate_medals(
        user_id, mode, score_breakdown.get("overall", 0.0), highest_difficulty, streak_state
    )
    history = interview_store.get_history(user_id)

    return jsonify({
        "score_breakdown": score_breakdown,
        "fairness_report": fairness_report,
        "recommendations": recommendations,
        "highest_difficulty_reached": highest_difficulty,
        "history": history,
        "streak": streak_state,
        "newly_awarded_medals": newly_awarded,
    })


@app.route("/api/interview/history", methods=["GET"])
@login_required
def interview_history():
    return jsonify({"history": interview_store.get_history(session["user_id"])})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

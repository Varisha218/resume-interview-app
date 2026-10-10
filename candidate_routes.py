"""Candidate-side API routes (resume, jobs board, applications).

Registered from app.py with `candidate_routes.init_app(app)`. Authentication
reuses the existing signup/login/logout routes in app.py (Flask session
cookie with `user_id`), so no separate candidate auth is needed.
"""

import functools

from flask import Blueprint, jsonify, request, session

from utils import candidate
from utils.candidate import CandidateError

bp = Blueprint("candidate", __name__, url_prefix="/api/candidate")


def _login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in to continue."}), 401
        return view(*args, **kwargs)
    return wrapped


@bp.errorhandler(CandidateError)
def _handle_candidate_error(err):
    body = {"error": str(err)}
    if err.code:
        body["code"] = err.code
    return jsonify(body), err.status


# ---------------------------------------------------------------------
# My Resume
# ---------------------------------------------------------------------

@bp.route("/profile", methods=["GET"])
@_login_required
def get_profile():
    return jsonify({"profile": candidate.get_profile(session["user_id"])})


@bp.route("/profile", methods=["PUT", "POST"])
@_login_required
def save_profile():
    data = request.get_json(force=True, silent=True) or {}
    profile = candidate.save_profile(session["user_id"], data)
    return jsonify({"profile": profile})


# ---------------------------------------------------------------------
# Jobs board
# ---------------------------------------------------------------------

@bp.route("/jobs", methods=["GET"])
@_login_required
def list_jobs():
    jobs = candidate.list_jobs(session["user_id"], request.args.get("q", ""))
    return jsonify({"jobs": jobs})


@bp.route("/jobs/<int:job_id>", methods=["GET"])
@_login_required
def get_job(job_id):
    job = candidate.get_job(session["user_id"], job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    return jsonify({"job": job})


@bp.route("/jobs/<int:job_id>/apply", methods=["POST"])
@_login_required
def apply(job_id):
    data = request.get_json(force=True, silent=True) or {}
    application = candidate.apply_to_job(
        session["user_id"], job_id, data.get("cover_note", "")
    )
    return jsonify({"application": application}), 201


# ---------------------------------------------------------------------
# My applications
# ---------------------------------------------------------------------

@bp.route("/applications", methods=["GET"])
@_login_required
def list_applications():
    return jsonify({"applications": candidate.list_applications(session["user_id"])})


def init_app(app):
    """Create the candidate tables (if missing) and register the routes."""
    candidate.init_schema()
    app.register_blueprint(bp)

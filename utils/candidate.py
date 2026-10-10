"""Candidate side: resume profile, job listing, and applications.

Owns the `candidate_profiles` and `applications` tables. The `jobs` table is
read-only from the candidate side's point of view (recruiters create jobs);
it is created here with IF NOT EXISTS only so the candidate flow can be tested
on its own. If the recruiter side already defines `jobs`, that definition wins
and this one is skipped.

Columns the candidate side relies on in `jobs`:
    id, title, company, location, job_type, description, skills, status,
    created_at          (status = 'open' means visible to candidates)
"""

import time

from psycopg2 import errors as pg_errors

from utils import db

MAX_SKILLS = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT,
    location TEXT,
    headline TEXT,
    summary TEXT,
    skills TEXT,
    education TEXT,
    experience TEXT,
    resume_text TEXT,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    job_type TEXT,
    description TEXT NOT NULL,
    skills TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'submitted',
    cover_note TEXT,
    resume_snapshot TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    UNIQUE (user_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
"""


class CandidateError(Exception):
    """Raised for user-facing problems. `status` is the HTTP status to return."""

    def __init__(self, message: str, status: int = 400, code: str = None):
        super().__init__(message)
        self.status = status
        self.code = code


def init_schema():
    with db.get_conn() as conn:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        cur.close()


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def split_skills(value) -> list:
    """'python, flask' / ['python', 'flask'] -> ['python', 'flask'] (deduped)."""
    if not value:
        return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    seen, out = set(), []
    for item in items:
        s = str(item).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def _clean(value, max_len: int, field: str, required: bool = False) -> str:
    text = (value or "")
    if not isinstance(text, str):
        raise CandidateError(f"{field} must be text.")
    text = text.strip()
    if required and not text:
        raise CandidateError(f"{field} is required.")
    if len(text) > max_len:
        raise CandidateError(f"{field} is too long (max {max_len} characters).")
    return text


def _profile_row(row) -> dict:
    d = dict(row)
    d["skills"] = split_skills(d.get("skills"))
    return d


def _resume_snapshot(profile: dict) -> str:
    """Text copy of the resume as it was when the candidate applied."""
    if profile.get("resume_text"):
        return profile["resume_text"]
    parts = [profile.get("full_name") or ""]
    if profile.get("headline"):
        parts.append(profile["headline"])
    contact = " | ".join(x for x in (profile.get("phone"), profile.get("location")) if x)
    if contact:
        parts.append(contact)
    if profile.get("summary"):
        parts.append("SUMMARY\n" + profile["summary"])
    if profile.get("skills"):
        parts.append("SKILLS\n" + ", ".join(profile["skills"]))
    if profile.get("experience"):
        parts.append("EXPERIENCE\n" + profile["experience"])
    if profile.get("education"):
        parts.append("EDUCATION\n" + profile["education"])
    return "\n\n".join(parts)


# ---------------------------------------------------------------------
# resume / profile
# ---------------------------------------------------------------------

def get_profile(user_id: int):
    with db.get_cursor() as cur:
        cur.execute("SELECT * FROM candidate_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
    return _profile_row(row) if row else None


def save_profile(user_id: int, data: dict) -> dict:
    full_name = _clean(data.get("full_name"), 120, "Full name", required=True)
    phone = _clean(data.get("phone"), 40, "Phone")
    location = _clean(data.get("location"), 120, "Location")
    headline = _clean(data.get("headline"), 160, "Headline")
    summary = _clean(data.get("summary"), 2000, "Summary")
    education = _clean(data.get("education"), 4000, "Education")
    experience = _clean(data.get("experience"), 6000, "Experience")
    resume_text = _clean(data.get("resume_text"), 30000, "Resume text")

    skills = split_skills(data.get("skills"))
    if len(skills) > MAX_SKILLS:
        raise CandidateError(f"Please list at most {MAX_SKILLS} skills.")
    if any(len(s) > 60 for s in skills):
        raise CandidateError("Each skill must be 60 characters or fewer.")

    with db.get_cursor() as cur:
        cur.execute(
            """INSERT INTO candidate_profiles
                   (user_id, full_name, phone, location, headline, summary,
                    skills, education, experience, resume_text, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (user_id) DO UPDATE SET
                   full_name = EXCLUDED.full_name,
                   phone = EXCLUDED.phone,
                   location = EXCLUDED.location,
                   headline = EXCLUDED.headline,
                   summary = EXCLUDED.summary,
                   skills = EXCLUDED.skills,
                   education = EXCLUDED.education,
                   experience = EXCLUDED.experience,
                   resume_text = EXCLUDED.resume_text,
                   updated_at = EXCLUDED.updated_at
               RETURNING *""",
            (user_id, full_name, phone, location, headline, summary,
             ", ".join(skills), education, experience, resume_text, time.time()),
        )
        row = cur.fetchone()
    return _profile_row(row)


# ---------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------

def _job_row(row) -> dict:
    d = dict(row)
    d["skills"] = split_skills(d.get("skills"))
    d["applied"] = bool(d.get("applied"))
    return d


def list_jobs(user_id: int, query: str = "", limit: int = 100) -> list:
    sql = """SELECT j.id, j.title, j.company, j.location, j.job_type,
                    j.description, j.skills, j.created_at,
                    (a.id IS NOT NULL) AS applied
             FROM jobs j
             LEFT JOIN applications a ON a.job_id = j.id AND a.user_id = %s
             WHERE j.status = 'open'"""
    params = [user_id]
    query = (query or "").strip()
    if query:
        like = f"%{query}%"
        sql += """ AND (j.title ILIKE %s OR j.company ILIKE %s OR j.location ILIKE %s
                        OR j.description ILIKE %s OR j.skills ILIKE %s)"""
        params += [like] * 5
    sql += " ORDER BY j.created_at DESC LIMIT %s"
    params.append(limit)

    with db.get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [_job_row(r) for r in rows]


def get_job(user_id: int, job_id: int):
    with db.get_cursor() as cur:
        cur.execute(
            """SELECT j.id, j.title, j.company, j.location, j.job_type,
                      j.description, j.skills, j.created_at,
                      (a.id IS NOT NULL) AS applied
               FROM jobs j
               LEFT JOIN applications a ON a.job_id = j.id AND a.user_id = %s
               WHERE j.id = %s AND j.status = 'open'""",
            (user_id, job_id),
        )
        row = cur.fetchone()
    return _job_row(row) if row else None


# ---------------------------------------------------------------------
# applications
# ---------------------------------------------------------------------

def apply_to_job(user_id: int, job_id: int, cover_note: str = "") -> dict:
    cover_note = _clean(cover_note, 2000, "Cover note")

    profile = get_profile(user_id)
    has_content = profile and (profile["skills"] or profile.get("experience")
                               or profile.get("resume_text") or profile.get("summary"))
    if not profile or not has_content:
        raise CandidateError(
            "Please complete and save your resume before applying.",
            status=400, code="resume_required",
        )

    if not get_job(user_id, job_id):
        raise CandidateError("That job is no longer available.", status=404)

    try:
        with db.get_cursor() as cur:
            cur.execute(
                """INSERT INTO applications
                       (user_id, job_id, status, cover_note, resume_snapshot, created_at)
                   VALUES (%s, %s, 'submitted', %s, %s, %s)
                   ON CONFLICT (user_id, job_id) DO NOTHING
                   RETURNING id, job_id, status, created_at""",
                (user_id, job_id, cover_note, _resume_snapshot(profile), time.time()),
            )
            row = cur.fetchone()
    except pg_errors.ForeignKeyViolation:
        raise CandidateError("That job is no longer available.", status=404)

    if not row:
        raise CandidateError("You have already applied to this job.", status=409)
    return dict(row)


def list_applications(user_id: int) -> list:
    with db.get_cursor() as cur:
        cur.execute(
            """SELECT a.id, a.job_id, a.status, a.cover_note, a.created_at,
                      j.title, j.company, j.location
               FROM applications a
               JOIN jobs j ON j.id = a.job_id
               WHERE a.user_id = %s
               ORDER BY a.created_at DESC""",
            (user_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]

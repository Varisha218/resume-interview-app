-- Step 4 of 5: candidate side tables - OWNED BY PERSON B:
--     candidate_profiles   (the "My Resume" data)
--     applications         (a candidate applying to a job)
-- Needs: users (step 2) and jobs (step 3, or the recruiter's own jobs table).
--     psql -U interview_user -d interview_coach -f database/04_candidate_tables.sql
-- Safe to run more than once. The app also creates these on startup.

CREATE TABLE IF NOT EXISTS candidate_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT,
    location TEXT,
    headline TEXT,
    summary TEXT,
    skills TEXT,            -- comma separated, e.g. 'Python, SQL'
    education TEXT,
    experience TEXT,
    resume_text TEXT,
    updated_at DOUBLE PRECISION NOT NULL
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

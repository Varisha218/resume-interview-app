-- Step 3 of 5: jobs table - OWNED BY THE RECRUITER SIDE, not by Person B.
-- The candidate tables below have a foreign key to jobs(id), so a jobs table
-- must exist first. Use this file ONLY if the recruiter side has not created
-- it yet. If they already have a jobs table, SKIP this file (and make sure
-- theirs has: id, title, company, location, job_type, description, skills,
-- status, created_at; status = 'open' means visible to candidates).
--     psql -U interview_user -d interview_coach -f database/03_jobs_table_dev_fallback.sql

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    job_type TEXT,
    description TEXT NOT NULL,
    skills TEXT,            -- comma separated
    status TEXT NOT NULL DEFAULT 'open',
    created_at DOUBLE PRECISION NOT NULL
);

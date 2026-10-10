-- Step 2 of 5: base app tables (already part of the project: login, interview
-- history, streaks, medals). NOT owned by the candidate side.
-- Run connected to interview_coach, as interview_user:
--     psql -U interview_user -d interview_coach -f database/02_base_tables.sql
-- Safe to run more than once. The app also creates these on startup.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    overall_score DOUBLE PRECISION NOT NULL,
    relevance_score DOUBLE PRECISION,
    structure_score DOUBLE PRECISION,
    fluency_score DOUBLE PRECISION,
    highest_difficulty_reached TEXT,
    question_count INTEGER,
    recommendations TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    practiced_date DATE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON interview_sessions(user_id);

CREATE TABLE IF NOT EXISTS streaks (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_practice_date DATE
);

CREATE TABLE IF NOT EXISTS medals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    icon TEXT NOT NULL,
    awarded_at DOUBLE PRECISION NOT NULL,
    UNIQUE(user_id, code)
);

-- Step 1 of 5: create the PostgreSQL user and database.
-- Run this as a superuser (e.g. the "postgres" user), connected to any database:
--     psql -U postgres -f database/01_create_database.sql
-- In pgAdmin: open Query Tool on the "postgres" database, paste this, run it.
--
-- The names/password match .env.example. Change the password for real use,
-- and keep DATABASE_URL in your .env in sync.

CREATE USER interview_user WITH PASSWORD 'interview_pass';

CREATE DATABASE interview_coach OWNER interview_user;

-- Step 5 of 5 (optional): 4 demo jobs so the candidate Jobs board has something to show
-- before the recruiter side can post jobs. Run after 03_jobs_table_dev_fallback.sql:
--     psql -U interview_user -d interview_coach -f database/05_seed_demo_jobs.sql
-- (Same data as scripts/seed_demo_jobs.py. Run only once, or you get duplicates.)

INSERT INTO jobs (title, company, location, job_type, description, skills, status, created_at) VALUES
('Junior Python Developer', 'Nova Labs', 'Islamabad', 'Full-time',
 E'Build and maintain Flask REST APIs backed by PostgreSQL.\nWrite clean, tested code and work with a small friendly team.',
 'Python, Flask, SQL, Git', 'open', EXTRACT(EPOCH FROM now())),
('Machine Learning Intern', 'Insight AI', 'Remote', 'Internship',
 E'Help train and evaluate NLP models for resume and interview analysis.\nYou will work with scikit-learn and sentence-transformers.',
 'Python, Machine Learning, NLP, scikit-learn', 'open', EXTRACT(EPOCH FROM now()) - 1),
('Frontend Developer', 'Pixel Studio', 'Rawalpindi', 'Full-time',
 'Turn designs into fast, accessible, responsive web interfaces using vanilla JavaScript or React.',
 'JavaScript, HTML, CSS, React', 'open', EXTRACT(EPOCH FROM now()) - 2),
('QA / Software Test Engineer', 'Quality First', 'Lahore', 'Full-time',
 'Design test plans, write automated tests, and report defects clearly.',
 'Software Testing, Selenium, Communication', 'open', EXTRACT(EPOCH FROM now()) - 3);

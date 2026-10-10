"""Optional: insert a few demo jobs so the candidate side can be tested on its
own (before the recruiter side can post jobs).

Run from the project root:   python scripts/seed_demo_jobs.py
Does nothing if the jobs table already has rows.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from utils import candidate, db  # noqa: E402

DEMO_JOBS = [
    ("Junior Python Developer", "Nova Labs", "Islamabad", "Full-time",
     "Build and maintain Flask REST APIs backed by PostgreSQL.\n"
     "Write clean, tested code and work with a small friendly team.",
     "Python, Flask, SQL, Git"),
    ("Machine Learning Intern", "Insight AI", "Remote", "Internship",
     "Help train and evaluate NLP models for resume and interview analysis.\n"
     "You will work with scikit-learn and sentence-transformers.",
     "Python, Machine Learning, NLP, scikit-learn"),
    ("Frontend Developer", "Pixel Studio", "Rawalpindi", "Full-time",
     "Turn designs into fast, accessible, responsive web interfaces using "
     "vanilla JavaScript or React.",
     "JavaScript, HTML, CSS, React"),
    ("QA / Software Test Engineer", "Quality First", "Lahore", "Full-time",
     "Design test plans, write automated tests, and report defects clearly.",
     "Software Testing, Selenium, Communication"),
]


def main():
    db.init_db()
    candidate.init_schema()
    with db.get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM jobs")
        if cur.fetchone()["n"]:
            print("jobs table already has rows - nothing to do.")
            return
        now = time.time()
        for i, (title, company, location, job_type, description, skills) in enumerate(DEMO_JOBS):
            cur.execute(
                """INSERT INTO jobs (title, company, location, job_type, description,
                                     skills, status, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 'open', %s)""",
                (title, company, location, job_type, description, skills, now - i),
            )
    print(f"Inserted {len(DEMO_JOBS)} demo jobs.")


if __name__ == "__main__":
    main()

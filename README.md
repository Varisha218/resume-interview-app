# AI Interview Coach (Local, Offline-first FYP)

A local web app that:
1. Takes your **resume** (PDF/DOCX/TXT or pasted text) and a **job description**.
2. Computes a **match percentage**, lists **matched skills** and **weaknesses (missing skills)**,
   plus resume improvement notes — using a real local sentence-embedding AI model
   (`sentence-transformers/all-MiniLM-L6-v2`, see `utils/semantic_model.py`) for semantic
   similarity and skill matching, combined with a built-in skills vocabulary
   (`utils/skills_db.py`) used only to spot candidate skill terms in the text.
   No API key, no external AI calls, no per-use cost — the model downloads once (~90MB)
   the first time you run the app, then runs fully offline from a local cache.
3. Lets you choose **Practice Interview** (feedback after each question) or **Mock Interview**
   (real-interview simulation, 5–7 minutes, feedback only at the end).
4. Generates interview questions offline, based on your matched/missing skills plus a
   behavioral question bank.
5. Runs a live interview with your **webcam**: detects face expressions
   (happy/neutral/sad/surprised/etc.) using `face-api.js` running entirely in your browser,
   detects **silence** via microphone volume to auto-advance stuck questions, and captures a
   live transcript via the browser's built-in speech recognition to score answer relevance
   and count filler words / speaking pace.
6. Shows a final **summary**: answer quality score, emotional engagement, eye-contact/
   camera-presence estimate, speaking pace, filler word count, and a per-question breakdown.

## How the matching became "real AI" instead of hardcoded rules
The previous version scored resumes using regex keyword lookups, a static per-skill
importance table, and a hand-written dictionary of "these skills count as synonyms of
each other." That's why it felt hardcoded — it was. It's been replaced with:
- **`utils/semantic_model.py`**: loads `all-MiniLM-L6-v2`, a pretrained sentence-embedding
  model, and exposes similarity helpers. This model was trained by the sentence-transformers
  team on over a billion sentence pairs to place semantically related text near each other
  in vector space — it's a genuine trained neural network, not a lookup table.
- **Skill matching**: instead of a fixed synonym dictionary, each JD skill is compared
  against every resume skill with the embedding model, so novel phrasings (e.g. "led a team
  of engineers" ↔ "leadership") are recognized on their own merits.
- **Skill importance**: instead of a static table saying e.g. "python = 10, html = 2", each
  skill's weight is now derived from how *this specific* job description mentions it
  (how often, and how early).
- **Overall resume/JD similarity**: instead of TF-IDF keyword overlap, the whole resume and
  JD are chunked, embedded, and compared with cosine similarity — capturing meaning, not just
  shared vocabulary.
- The skills vocabulary (`skills_db.py`) still exists, but only to spot candidate skill terms
  in free text (a taxonomy, not a verdict) — there's no offline model in scope here for full
  open-ended skill extraction (that would need a trained NER model with labeled data).

7. Requires an **account** (login/signup) before any interview can be started — the cover
   screen's "Begin Analysis" button routes to a login/sign-up screen, then into a **Profile**
   hub showing your **practice streak** (consecutive days practiced) and **medals** (earned for
   milestones like your first session, streaks, high scores, and completing a mock interview).
   Interview history, streaks, and medals are all persisted in **PostgreSQL**, keyed to your
   account, so they carry over across sessions/devices.

## Tech stack
- Backend: Python + Flask, sentence-transformers (local embedding model), pdfplumber, python-docx
- Auth: Flask signed-cookie sessions + `werkzeug.security` password hashing (PBKDF2) — no
  plaintext passwords stored, no third-party auth provider
- Database: **PostgreSQL** via `psycopg2` (users, interview history, streaks, medals)
- Frontend: vanilla HTML/CSS/JS
- Face analysis: face-api.js (loaded from CDN, runs locally in-browser)
- Speech-to-text: browser's native SpeechRecognition API (Chrome recommended)


## Setup

### 1. Install PostgreSQL and create a database

If you don't already have PostgreSQL installed:
- **macOS**: `brew install postgresql@16 && brew services start postgresql@16`
- **Ubuntu/Debian**: `sudo apt install postgresql && sudo systemctl start postgresql`
- **Windows**: install from https://www.postgresql.org/download/windows/
- Or run it in Docker instead of installing anything locally:
  ```bash
  docker run --name interview-coach-db -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=interview_coach -p 5432:5432 -d postgres:16
  ```

If you installed Postgres natively (not via the Docker command above), create the database:
```bash
createdb interview_coach
# or, from the psql prompt:  CREATE DATABASE interview_coach;
```

The app creates its own tables (`users`, `interview_sessions`, `streaks`, `medals`)
automatically on first run — no migration step needed.

### 2. Configure the connection

Set a `DATABASE_URL` environment variable (or leave it unset to use the default
`postgresql://postgres:postgres@localhost:5432/interview_coach`, which matches the Docker
command above):

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/interview_coach"
export SECRET_KEY="pick-a-long-random-string"   # signs the login session cookie
```

(On Windows PowerShell: `$env:DATABASE_URL = "..."`.)

### 3. Install Python dependencies and run

```bash
cd resume_interview_app
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in **Google Chrome** (recommended — best support for
webcam, microphone, and live speech-to-text).

Click **Begin Analysis**, create an account (or log in), and you'll land on your **Profile**
page — from there, **Start New Interview** walks through the resume/JD upload and analysis as
before, then Practice/Mock as usual. Finishing a session updates your streak, checks for newly
earned medals, and shows both on the summary screen before you head back to your profile.

When prompted, allow **camera and microphone access**.

## Important notes / limitations (be upfront about these in your FYP report/demo)

- **face-api.js models** are loaded from a CDN (`cdn.jsdelivr.net`) the first time you run an
  interview, so you need an internet connection for that one-time model download in your
  browser (they get cached afterward by the browser). The face/emotion *processing* itself
  runs 100% locally on your machine — no images or video are ever uploaded anywhere.
- **Speech-to-text** uses the browser's built-in `webkitSpeechRecognition`, which is best
  supported in Google Chrome. Some Chromium versions route recognition through Google's
  servers in the background; this is a browser-level behavior, not something this app controls.
  If you need a fully offline STT for your report, you can swap this for a local engine like
  **Vosk** (Python) — this would require sending short audio chunks to a new Flask endpoint
  instead of using `SpeechRecognition` in JS. Happy to help you add that if needed.
- The "correctness" scoring is a **keyword-overlap heuristic** (transcript vs. expected
  keywords per question) since everything is offline — it's a reasonable proxy for an FYP demo,
  not a full NLP semantic grader.
- "Stutter detection" is approximated via **filler-word counts** and **speaking pace (WPM)**,
  not true disfluency/audio-based stutter detection (which needs a specialized audio model).
- Silence auto-skip triggers after **8 seconds** of low mic volume — tweak
  `SILENCE_SKIP_SECONDS` and `VOLUME_THRESHOLD` in `static/js/interview.js` to taste.

## Project structure

```
resume_interview_app/
├── app.py                     # Flask backend & API routes
├── requirements.txt
├── utils/
│   ├── db.py                  # PostgreSQL connection pool + schema init
│   ├── auth.py                # Signup/login, password hashing
│   ├── gamification.py        # Streaks + medal catalog/awarding
│   ├── interview_store.py     # Interview history persistence (Postgres)
│   ├── resume_parser.py       # PDF/DOCX/TXT text extraction
│   ├── matcher.py             # Embedding-model + skill-based match scoring
│   ├── skills_db.py           # Skills vocabulary (extraction taxonomy only)
│   ├── semantic_model.py      # Local sentence-embedding model (all-MiniLM-L6-v2)
│   └── question_bank.py       # Offline question generation
├── templates/
│   └── index.html             # Single-page app shell (cover, auth, profile, upload...)
└── static/
    ├── css/style.css
    └── js/
        ├── cover.js           # Cover screen -> routes into auth/profile
        ├── auth.js            # Login/signup, session check, profile rendering
        ├── app.js             # Navigation, upload, analysis rendering
        └── interview.js       # Webcam, face-api, silence detection, speech, scoring
```

## Extending for your FYP

- Add more entries to `SKILLS_DB` in `utils/skills_db.py` for your target domain.
- Add more templates to `GENERIC_QUESTIONS` / skill-question templates in
  `utils/question_bank.py`.
- Swap the keyword-overlap scoring in `interview.js` for a local embedding-similarity model
  (e.g. `sentence-transformers` running in a Flask endpoint) if you want a stronger "semantic"
  correctness score to highlight in your defense.

# Dizzy Ducks — Gig Marketplace

[![Web CI/CD](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/web.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/web.yml)
[![Worker CI/CD](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/worker.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/worker.yml)

Dizzy Ducks is a campus gig marketplace where students can post short-term jobs, apply to gigs, and receive email notifications when opportunities matching their interests are posted. It is built with Flask, MongoDB, and a standalone email notification worker.

## Team

- [antoniojacksnn](https://github.com/antoniojacksnn)
- [FilthyS](https://github.com/FilthyS)
- [harrisonmangitwong](https://github.com/harrisonmangitwong)
- [sashacartagena](https://github.com/sashacartagena)
- [ClaireBocz](https://github.com/ClaireBocz)

## Features

- Sign up, log in, and choose job category tags during onboarding
- Browse and search open gigs by keyword or category tag
- Post gigs with title, category, pay, location, date, description, and optional custom questions
- Poster dashboard: view all posted gigs and incoming applications; accept or reject applicants
- Apply to gigs with a message and answers to any required questions
- Applicant dashboard: track every application and its current status
- Email notifications via SendGrid for new gig matches, application receipts, status changes, and weekly digests
- Profile page: update name, tags, and email notification preferences

## Architecture

| Subsystem | Technology | Responsibility |
| --- | --- | --- |
| Web app | Flask + Python 3.10 | Authentication, gig posting, browsing, applications, dashboards, profile |
| Database | MongoDB 7 | Users, gigs, applications, notification queue |
| Email worker | Python 3.12 | Polls MongoDB, sends emails via SendGrid, marks notifications sent/failed |

## Quick Start (Docker Compose)

### 1. Clone the repository

```bash
git clone https://github.com/swe-students-spring2026/5-final-dizzy-ducks.git
cd 5-final-dizzy-ducks
```

### 2. Create environment files

Copy the example files and fill in your values:

```bash
cp web/.env.example web/.env
cp email-worker/.env.example email-worker/.env
```

See [Environment Variables](#environment-variables) below for what each variable means.

### 3. Start all services

```bash
docker compose up --build
```

The web app will be available at **http://localhost:5001**.

To run in the background:

```bash
docker compose up --build -d
```

To stop:

```bash
docker compose down
```

## Local Web App Development (without Docker)

The Python environment is managed with Pipenv. Python 3.10 is required.

```bash
pipenv install --dev
pipenv run dev
```

If you see `pipenv: command not found`, either add `export PATH="$HOME/.local/bin:$PATH"` to your shell config (pip installs the binary there) or use `python -m pipenv install --dev` and `python -m pipenv run dev` instead.

The web app runs at `http://127.0.0.1:5000`.

If `MONGO_URI` is not set, the app starts with an in-memory repository and seeds it with sample gigs automatically, so no MongoDB instance is needed for basic development.

Run quality checks before committing:

```bash
pipenv run lint
pipenv run test
```

## Local Email Worker Development

```bash
cd email-worker
pip install -r requirements.txt
python email_worker.py
```

Run worker tests:

```bash
cd email-worker
pytest tests/ --cov=email_worker --cov-report=term-missing
```

## Environment Variables

### Web app (`web/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Flask session signing secret. Use a long random string in production. |
| `MONGO_URI` | No | MongoDB connection string. Defaults to `mongodb://mongo:27017` (Docker) or in-memory when unset. |
| `MONGO_DB` | No | Database name. Defaults to `campus_gigs`. |
| `ENABLE_DEV_AUTH` | No | Set to `1` to enable the dev login bypass at `/auth/dev-login`. **Never enable in production.** |

### Email worker (`email-worker/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `MONGO_URI` | Yes | MongoDB connection string, e.g. `mongodb://mongo:27017` or an Atlas URI. |
| `MONGO_DB` | No | Database name. Defaults to `campus_gigs`. |
| `SENDGRID_API_KEY` | Yes | SendGrid API key for email delivery. Get one at [sendgrid.com](https://sendgrid.com). |
| `FROM_EMAIL` | Yes | Sender address used for all outgoing emails. |
| `POLL_INTERVAL` | No | Seconds between polling runs. Defaults to `60`. |

### Example `web/.env`

```env
SECRET_KEY=replace-with-a-long-random-secret
MONGO_URI=mongodb://mongo:27017
MONGO_DB=campus_gigs
ENABLE_DEV_AUTH=1
```

### Example `email-worker/.env`

```env
MONGO_URI=mongodb://mongo:27017
MONGO_DB=campus_gigs
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=noreply@yourdomain.com
POLL_INTERVAL=60
```

## Importing Starter Data

The web app seeds a small set of sample gigs automatically when running in in-memory mode (no `MONGO_URI`). For a production MongoDB instance, seed data can be inserted manually. A future `seed.py` script can be added to `web/` if needed.

## Project Structure

```text
.
├── web/                    # Flask web app
│   ├── app/                # Application package
│   │   ├── blueprints/     # Route handlers (gigs, management, profile, dev_auth)
│   │   ├── templates/      # Jinja2 templates specific to blueprints
│   │   ├── utils/          # Auth helpers
│   │   └── db.py           # MongoDB connection helpers
│   ├── templates/          # Top-level Jinja2 templates (auth, dashboard, onboarding)
│   ├── static/css/         # Stylesheet
│   ├── auth.py             # Auth blueprint (signup, login, logout)
│   ├── dashboard.py        # Dashboard blueprint
│   ├── onboarding.py       # Onboarding blueprint
│   ├── repositories.py     # InMemoryRepository and MongoRepository
│   ├── tags.py             # Job tag definitions
│   ├── wsgi.py             # WSGI entry point
│   ├── Dockerfile
│   └── .env.example
├── email-worker/           # Standalone notification worker
│   ├── email_worker.py     # Worker logic
│   ├── tests/
│   ├── Dockerfile
│   └── .env.example
├── tests/                  # Web app tests (InMemory)
├── web/tests/              # Web app tests (mongomock)
├── docker-compose.yml
├── pyproject.toml
└── Pipfile
```

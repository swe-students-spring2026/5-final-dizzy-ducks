# Dizzy Ducks — Gig Marketplace

[![Web CI/CD](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/web.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/web.yml)
[![Worker CI/CD](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/worker.yml/badge.svg)](https://github.com/swe-students-spring2026/5-final-dizzy-ducks/actions/workflows/worker.yml)

Gigboard is a campus gig marketplace built for students. Users can post short-term jobs, browse and apply to open gigs, and get email notifications when new opportunities match their interests. The platform is powered by a Flask web app, a MongoDB database, and a dedicated email notification worker that runs independently in the background.

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
- Email notifications via SendGrid for new gig matches, application receipts, and status changes
- Profile page: update name, tags, and email notification preferences

> **Note on email delivery:** On the live deployed site, emails are sent once daily at 9:00 AM UTC to stay within free-tier limits — free deployment platforms do not support multiple email batches per day. The original design polls MongoDB every 60 seconds for near-immediate delivery, but that behavior is only available when running locally with Docker Compose (`docker compose up --build`).

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

If `pipenv: command not found` appears, add `export PATH="$HOME/.local/bin:$PATH"` to your shell config (pip installs the binary there), or run `python -m pipenv install --dev` and `python -m pipenv run dev` as an alternative.

The web app is available at `http://127.0.0.1:5001`.

Without `MONGO_URI` set, the app runs using an in-memory repository pre-loaded with sample gigs — no MongoDB setup required for basic development.

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

## Architecture

| Subsystem | Technology | Responsibility |
| --- | --- | --- |
| Web app | Flask + Python 3.10 | Authentication, gig posting, browsing, applications, dashboards, profile |
| Database | MongoDB 7 | Users, gigs, applications, notification queue |
| Email worker | Python 3.12 | Polls MongoDB, sends emails via SendGrid, marks notifications sent/failed |


## Environment Variables

### Web app (`web/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `MONGO_DB` | No | Database name. Defaults to `campus_gigs`. |
| `SECRET_KEY` | Yes | Flask session signing secret. Use a long random string in production. |
| `ENABLE_DEV_AUTH` | No | Set to `1` to enable the dev login bypass at `/auth/dev-login`. **Never enable in production.** |
| `MONGO_URI` | No | MongoDB connection string. Defaults to `mongodb://mongo:27017` (Docker) or in-memory when unset. |

### Email worker (`email-worker/.env`)

| Variable | Required | Description |
| --- | --- | --- |
| `MONGO_URI` | Yes | MongoDB connection string, e.g. `mongodb://mongo:27017` or an Atlas URI. |
| `MONGO_DB` | No | Database name. Defaults to `campus_gigs`. |
| `FROM_EMAIL` | Yes | Sender address used for all outgoing emails. |
| `SENDGRID_API_KEY` | Yes | SendGrid API key for email delivery. Get one at [sendgrid.com](https://sendgrid.com). |
| `POLL_INTERVAL` | No | Seconds between polling runs. Defaults to `60`. |

### Example `email-worker/.env`

```env
MONGO_URI=mongodb://mongo:27017
MONGO_DB=campus_gigs
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FROM_EMAIL=nyugigs@hotmail.com
POLL_INTERVAL=60
```

### Example `web/.env`

```env
SECRET_KEY=replace-with-a-long-random-secret
MONGO_URI=mongodb://mongo:27017
MONGO_DB=campus_gigs
ENABLE_DEV_AUTH=1
```



## Deployment (Vercel)

The app is live at **[https://dizzy-ducks-gigboard.vercel.app](https://dizzy-ducks-gigboard.vercel.app)**.

The Flask web app runs as a Python Serverless Function and the email notification worker runs as a **Vercel Cron** job (daily at 09:00 UTC). Both are defined in the repository root and deploy in a single `vercel --prod` step.

### Architecture on Vercel

| Component | How it runs |
| --- | --- |
| Web app (`api/index.py`) | Python Serverless Function — all HTTP requests rewritten here by `vercel.json` |
| Email worker (`web/app/blueprints/notify.py`) | `GET /api/notify` triggered daily by Vercel Cron; sends pending notifications via SendGrid |

### Deploy manually

```bash
npm install -g vercel@latest   # one-time install
vercel --prod                  # deploys from repo root
```

### Required Vercel environment variables

Set these in the [Vercel dashboard → Settings → Environment Variables](https://vercel.com/antonio-1cdd85f0/dizzy-ducks-gigboard/settings/environment-variables):

| Variable | Required | Description |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Long random string for Flask session signing |
| `MONGO_URI` | Yes (prod) | MongoDB Atlas connection string, e.g. `mongodb+srv://…` |
| `MONGO_DB` | No | Database name. Defaults to `campus_gigs` |
| `SENDGRID_API_KEY` | Yes | SendGrid API key — enables email notifications |
| `FROM_EMAIL` | No | Sender address. Set to `nyugigs@hotmail.com` for production. |

> Without `MONGO_URI`, the app runs in **in-memory mode** (data resets on each cold start). Set `MONGO_URI` to a MongoDB Atlas cluster for persistent data.

> Without `SENDGRID_API_KEY`, the cron job skips sending and logs a warning — no errors thrown.

### GitHub Actions auto-deploy

Push to `main` → tests pass → Vercel production deployment is triggered automatically.

Add these three secrets to GitHub → Settings → Secrets → Actions:

| Secret | Where to find it |
| --- | --- |
| `VERCEL_TOKEN` | [Vercel Account Settings → Tokens](https://vercel.com/account/tokens) |
| `VERCEL_ORG_ID` | `.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | `.vercel/project.json` → `projectId` |

Also add `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` to build and push Docker images to Docker Hub on each merge.

---

## Importing Starter Data

The web app seeds a small set of sample gigs automatically when running in in-memory mode (no `MONGO_URI`). For a production MongoDB instance, seed data can be inserted manually. A future `seed.py` script can be added to `web/` if needed.


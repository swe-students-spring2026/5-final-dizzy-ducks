# Dizzy Ducks

Dizzy Ducks is a Flask + MongoDB gig marketplace where users can post short-term jobs, search for gigs, apply with a message, manage applications, and receive email notifications through a standalone worker service.

This README is the shared project structure so the team can stay aligned while building.

## Project Scope

Users should be able to:

- sign up and log in
- choose job tags during onboarding
- update skills, tags, and notification preferences from their profile
- post a gig with a title, category, pay, location, date, and description
- browse gigs by category
- search gigs by keyword
- view a full gig description page
- apply to a gig with a short message
- see a dashboard of gigs they posted and incoming applications
- see a dashboard of gigs they applied to and their current status
- accept or reject applicants for gigs they posted

## Core Subsystems

| Subsystem | Technology | Responsibility |
| --- | --- | --- |
| Web App | Flask | Handles authentication, onboarding, gig posting, gig search, applications, dashboards, and profile settings |
| Database | MongoDB | Stores users, gigs, applications, and notification queue records |
| Notification Worker | Python service in a separate container | Polls MongoDB, creates notification records, sends email, and marks notifications as sent |

## Screens

| Screen | Purpose | Main Actions |
| --- | --- | --- |
| Log In / Sign Up | User entry point | Create account, log in |
| Onboarding / Tags | Initial preference setup | Select job categories/tags for matching and notifications |
| Dashboard / Home | Main landing page | Browse gigs, filter by tags, search by keyword or category |
| Job Description | Single gig detail page | View gig details and apply with a short message |
| Job Tracker | Application and posting overview | View jobs applied to, application statuses, and jobs posted |
| Posted Jobs | Poster management page | See all gigs posted by the current user |
| Posted Job Applicants | Applicant review page | View applicants, history, stars, job count, and accept/reject decisions |
| User Profile | Account and preferences page | Update name, email, skills, tags, and notification settings |

## MongoDB Collections

### `users`

Stores account, profile, skills, and notification settings.

| Field | Description |
| --- | --- |
| `name` | User display name |
| `email` | User email address |
| `skills` | Skills listed by the user |
| `notification_preferences` | Saved categories/tags and email preferences |

Example notification preferences:

```json
{
  "tags": ["tutoring", "delivery"],
  "new_gig_alerts": true,
  "application_alerts": true,
  "status_alerts": true,
  "weekly_digest": true
}
```

### `gigs`

Stores posted gigs.

| Field | Description |
| --- | --- |
| `title` | Gig title |
| `category` | Gig category/tag |
| `pay` | Pay amount or pay description |
| `location` | Gig location |
| `date` | Date of the gig |
| `description` | Full gig description |
| `poster_id` | User ID of the poster |
| `status` | `open` or `filled` |
| `created_at` | Timestamp when the gig was created |

### `applications`

Stores applications submitted by users.

| Field | Description |
| --- | --- |
| `gig_id` | Gig being applied to |
| `applicant_id` | User ID of the applicant |
| `message` | Short application message |
| `status` | `pending`, `accepted`, or `rejected` |
| `applied_at` | Timestamp when the application was submitted |

### `notifications`

Acts as the queue of pending emails the notification worker needs to send.

| Field | Description |
| --- | --- |
| `user_id` | User who should receive the email |
| `type` | Notification type, such as `new_gig`, `application`, `status`, or `weekly_digest` |
| `status` | `pending`, `sent`, or `failed` |
| `subject` | Email subject |
| `body` | Email body |
| `created_at` | Timestamp when the notification was queued |
| `scheduled_for` | Optional timestamp for delayed or digest emails |
| `sent_at` | Timestamp after successful delivery |
| `provider_message_id` | Optional SendGrid/SMTP provider message ID |
| `dedupe_key` | Unique key to prevent duplicate sends |

## Notification Worker

The notification worker is a standalone Python service running in its own container. It wakes up every configurable number of minutes and runs notification jobs.

| Job | Behavior |
| --- | --- |
| New Gig Alerts | Checks whether new gigs match a user's saved preferences, such as tutoring gigs, then queues an email |
| Application Alerts | Emails a gig poster when someone applies to their gig |
| Status Alerts | Emails an applicant when a poster accepts or rejects their application |
| Weekly Digest | Every Monday morning, sends each user a summary of new gigs that fit their profile |
| Email Sending | Sends pending emails through SendGrid or SMTP and marks them as sent in MongoDB |

Worker requirements:

- poll MongoDB every `X` minutes, controlled by configuration
- create queued notification records before sending
- send only notifications that are still pending
- respect each user's notification preferences
- mark notifications as `sent` after successful delivery
- mark notifications as `failed` when delivery fails
- use a `dedupe_key` so the same email is never sent twice

## Email Delivery

SendGrid is the planned email provider.

SendGrid is a dedicated email delivery service owned by Twilio and built for apps that send automated emails. The app uses an API key and sends emails through the SendGrid API or Python SDK.

Why SendGrid fits this project:

- free tier gives 100 emails per day, enough for a class project
- more reliable delivery than basic SMTP
- better production path for automated emails
- supports tracking such as open rates and click rates
- slightly more setup, but cleaner to use in application code

## Suggested Environment Variables

| Variable | Purpose |
| --- | --- |
| `MONGODB_URI` | MongoDB connection string |
| `MONGODB_DB_NAME` | MongoDB database name |
| `FLASK_SECRET_KEY` | Flask session secret |
| `SENDGRID_API_KEY` | SendGrid API key |
| `MAIL_FROM_ADDRESS` | Sender email address |
| `WORKER_POLL_MINUTES` | How often the worker wakes up |
| `DIGEST_DAY` | Weekly digest day, expected value: `monday` |
| `DIGEST_HOUR` | Hour when weekly digest emails should be queued |

## Local Web App Development

The Python environment is managed with Pipenv. Use Python 3.10.

```bash
pipenv install --dev
pipenv run dev
```

The web app runs at `http://127.0.0.1:5000`. If `MONGODB_URI` is not set, the app uses an in-memory repository for local development.

Run quality checks before committing web app changes:

```bash
pipenv run lint
pipenv run test
```

## Recommended Repo Structure

```text
.
├── web/
│   ├── Dockerfile
│   └── ...
├── worker/
│   ├── Dockerfile
│   └── ...
├── .github/
│   └── workflows/
├── README.md
└── instructions.md
```

## Build Checklist

- scaffold the Flask web app
- create MongoDB connection utilities and collection helpers
- implement sign up, log in, and onboarding
- implement user profile settings for skills, tags, and notifications
- implement gig posting
- implement gig browsing, category filtering, and keyword search
- implement gig detail pages
- implement application submission
- implement applicant and poster dashboards
- implement accept/reject application flow
- create the notification worker service
- connect SendGrid or SMTP email delivery
- add Dockerfiles for custom subsystems
- add GitHub Actions workflows for custom subsystems
- document local environment setup and deployment steps

## Current Assumptions

- Tags selected during onboarding are stored in `users.notification_preferences.tags`.
- Gig status starts as `open` and becomes `filled` after an accepted applicant is chosen.
- Application status starts as `pending` and changes to `accepted` or `rejected`.
- Applicant history can start with basic profile data, skills, stars, and completed job count.
- Weekly digest emails are sent Monday morning and include matching gigs created since the previous digest.

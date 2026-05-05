"""
Vercel Serverless Function — email notification cron worker.

This file is only invoked directly if Vercel's routing bypasses the Flask
catch-all (e.g. during local `vercel dev`).  In production, the Flask rewrite
`/(.*) -> /api/index` sends all requests (including GET /api/notify from the
Vercel Cron) to the Flask app, which handles them in
web/app/blueprints/notify.py.

Keeping this file ensures:
  - The cron target path /api/notify is always resolvable by Vercel even if
    the rewrite is misconfigured.
  - Local `vercel dev` can invoke the worker without booting Flask.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

import sendgrid
from pymongo import MongoClient
from sendgrid.helpers.mail import Mail

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --------------------------------------------------------------------------- #
# DB helpers                                                                    #
# --------------------------------------------------------------------------- #

def _get_db():
    client = MongoClient(os.environ["MONGO_URI"])
    return client[os.environ.get("MONGO_DB", "campus_gigs")]


# --------------------------------------------------------------------------- #
# Worker tick                                                                   #
# --------------------------------------------------------------------------- #

def _run_tick() -> tuple[int, int]:
    db = _get_db()
    now = datetime.now(timezone.utc)
    pending = list(db.notifications.find({
        "status": "pending",
        "$or": [
            {"scheduled_for": None},
            {"scheduled_for": {"$exists": False}},
            {"scheduled_for": {"$lte": now}},
        ],
    }))

    api_key = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ.get("FROM_EMAIL", "noreply@gigboard.app")
    sent = failed = 0

    for n in pending:
        user = db.users.find_one({"_id": n["to_user_id"]}, {"email": 1})
        to_email = user.get("email") if user else None
        if not to_email:
            db.notifications.update_one({"_id": n["_id"]}, {"$set": {"status": "failed"}})
            failed += 1
            continue

        subject, body = _format(n)
        try:
            sg = sendgrid.SendGridAPIClient(api_key)
            msg = Mail(from_email=from_email, to_emails=to_email,
                       subject=subject, plain_text_content=body)
            resp = sg.send(msg)
            if resp.status_code == 202:
                db.notifications.update_one(
                    {"_id": n["_id"]},
                    {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc),
                              "provider_message_id": resp.headers.get("X-Message-Id")}},
                )
                sent += 1
            else:
                db.notifications.update_one({"_id": n["_id"]}, {"$set": {"status": "failed"}})
                failed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"sendgrid error: {exc}")
            db.notifications.update_one({"_id": n["_id"]}, {"$set": {"status": "failed"}})
            failed += 1

    return sent, failed


def _format(n: dict) -> tuple[str, str]:
    if n.get("subject") and n.get("body"):
        return n["subject"], n["body"]
    gig_title = n.get("payload", {}).get("gig_title", "a gig")
    templates = {
        "new_gig": ("New Gig Matches Your Preferences",
                    f"A new gig matching your preferences was posted: '{gig_title}'.\n\nLog in to GigBoard to apply."),
        "new_application": ("Someone Applied to Your Gig",
                            f"Someone applied to your gig '{gig_title}'.\n\nLog in to review."),
        "status_change": ("Application Update",
                          f"There's an update on your application for '{gig_title}'.\n\nLog in for details."),
        "weekly_digest": ("Your Weekly GigBoard Digest",
                          "Here's your weekly summary of new gigs.\n\nLog in to browse and apply."),
    }
    return templates.get(n.get("type", ""), ("GigBoard Notification", "You have a new notification."))


# --------------------------------------------------------------------------- #
# Vercel handler                                                                #
# --------------------------------------------------------------------------- #

class handler(BaseHTTPRequestHandler):
    def _check_auth(self) -> bool:
        secret = os.environ.get("CRON_SECRET", "")
        if not secret:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {secret}"

    def do_GET(self):
        if not self._check_auth():
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        if not os.environ.get("SENDGRID_API_KEY"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"skipped: SENDGRID_API_KEY not configured")
            return

        try:
            sent, failed = _run_tick()
            body = f"sent={sent} failed={failed}".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:  # noqa: BLE001
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode())

    def do_POST(self):
        self.do_GET()

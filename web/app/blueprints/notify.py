import os
from datetime import datetime, timezone

import sendgrid
from flask import Blueprint, jsonify, request
from sendgrid.helpers.mail import Mail

from ..db import get_db

bp = Blueprint("notify", __name__)


def _get_pending_notifications(db):
    now = datetime.now(timezone.utc)
    return list(db.notifications.find({
        "status": "pending",
        "$or": [
            {"scheduled_for": None},
            {"scheduled_for": {"$exists": False}},
            {"scheduled_for": {"$lte": now}},
        ]
    }))


def _get_user_email(db, user_id):
    user = db.users.find_one({"_id": user_id}, {"email": 1})
    return user.get("email") if user else None


def _mark_as_sent(db, notification_id, provider_message_id=None):
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {
            "status": "sent",
            "sent_at": datetime.now(timezone.utc),
            "provider_message_id": provider_message_id,
        }}
    )


def _mark_as_failed(db, notification_id):
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {"status": "failed"}}
    )


def _format_notification(n):
    subject = n.get("subject")
    body = n.get("body")
    if subject and body:
        return subject, body

    gig_title = n.get("payload", {}).get("gig_title", "a gig")
    templates = {
        "new_gig": (
            "New Gig Matches Your Preferences",
            f"Hi,\n\nA new gig was posted that matches your preferences: '{gig_title}'.\n\nLog in to GigBoard to apply.\n\nThe GigBoard Team"
        ),
        "new_application": (
            "Someone Applied to Your Gig",
            f"Hi,\n\nSomeone applied to your gig '{gig_title}'.\n\nLog in to GigBoard to review their application.\n\nThe GigBoard Team"
        ),
        "status_change": (
            "Application Update",
            f"Hi,\n\nThere's been an update on your application for '{gig_title}'.\n\nLog in to GigBoard for details.\n\nThe GigBoard Team"
        ),
        "weekly_digest": (
            "Your Weekly GigBoard Digest",
            "Hi,\n\nHere's your weekly summary of new gigs on GigBoard.\n\nLog in to browse and apply.\n\nThe GigBoard Team"
        ),
    }

    notification_type = n.get("type")
    if notification_type in templates:
        return templates[notification_type]
    return "GigBoard Notification", "You have a new notification."


def _send_email(to, subject, body):
    sg = sendgrid.SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    message = Mail(
        from_email=os.environ.get("FROM_EMAIL", "noreply@gigboard.com"),
        to_emails=to,
        subject=subject,
        plain_text_content=body,
    )
    response = sg.send(message)
    return response.status_code, response.headers.get("X-Message-Id")


@bp.post("/notify")
def notify():
    secret = os.environ.get("CRON_SECRET")
    if secret and request.headers.get("Authorization") != f"Bearer {secret}":
        return jsonify({"error": "unauthorized"}), 401

    db = get_db()
    notifications = _get_pending_notifications(db)
    sent, failed = 0, 0

    for n in notifications:
        to_email = _get_user_email(db, n["to_user_id"])
        if not to_email:
            _mark_as_failed(db, n["_id"])
            failed += 1
            continue
        subject, body = _format_notification(n)
        status_code, message_id = _send_email(to_email, subject, body)
        if status_code == 202:
            _mark_as_sent(db, n["_id"], provider_message_id=message_id)
            sent += 1
        else:
            _mark_as_failed(db, n["_id"])
            failed += 1

    return jsonify({"sent": sent, "failed": failed})

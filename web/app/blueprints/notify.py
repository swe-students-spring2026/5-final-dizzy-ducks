"""
Cron endpoint for the notification worker.

Vercel calls GET /api/notify on the configured schedule.  The Flask rewrite
routes that request here.  The endpoint drains the pending notifications queue
and sends emails via SendGrid.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("notify", __name__)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Route                                                                         #
# --------------------------------------------------------------------------- #

@bp.get("/api/notify")
def notify():
    """Called by Vercel Cron every 5 minutes."""
    cron_secret = os.environ.get("CRON_SECRET", "")
    auth_header = request.headers.get("authorization", "")
    # When CRON_SECRET is set, only Vercel-signed requests are allowed.
    if cron_secret and auth_header != f"Bearer {cron_secret}":
        return jsonify({"error": "Unauthorized"}), 401

    sendgrid_key = os.environ.get("SENDGRID_API_KEY", "")
    if not sendgrid_key:
        logger.warning("SENDGRID_API_KEY not set — skipping notification batch")
        return jsonify({"skipped": True, "reason": "SENDGRID_API_KEY not configured"})

    db = current_app.extensions.get("mongo_db")
    if db is None:
        return jsonify({"error": "Database not available"}), 503

    try:
        sent, failed = _run_batch(db, sendgrid_key)
        logger.info("notify batch: sent=%d failed=%d", sent, failed)
        return jsonify({"sent": sent, "failed": failed})
    except Exception as exc:  # noqa: BLE001
        logger.error("notify batch error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# --------------------------------------------------------------------------- #
# Worker logic                                                                  #
# --------------------------------------------------------------------------- #

def _run_batch(db, sendgrid_key: str) -> tuple[int, int]:
    """Fetch pending notifications and send them.  Returns (sent, failed)."""
    import sendgrid as sg_mod  # noqa: PLC0415
    from sendgrid.helpers.mail import Mail  # noqa: PLC0415

    from_email = os.environ.get("FROM_EMAIL", "noreply@gigboard.app")
    now = datetime.now(timezone.utc)

    pending = list(db.notifications.find({
        "status": "pending",
        "$or": [
            {"scheduled_for": None},
            {"scheduled_for": {"$exists": False}},
            {"scheduled_for": {"$lte": now}},
        ],
    }))

    sent = failed = 0
    for n in pending:
        user = db.users.find_one({"_id": n["to_user_id"]}, {"email": 1})
        to_email = user.get("email") if user else None

        if not to_email:
            _mark_failed(db, n["_id"])
            failed += 1
            continue

        subject, body = _format(n)
        try:
            client = sg_mod.SendGridAPIClient(sendgrid_key)
            message = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
            )
            response = client.send(message)
            if response.status_code == 202:
                _mark_sent(db, n["_id"], response.headers.get("X-Message-Id"))
                sent += 1
            else:
                _mark_failed(db, n["_id"])
                failed += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("sendgrid error for %s: %s", n["_id"], exc)
            _mark_failed(db, n["_id"])
            failed += 1

    return sent, failed


def _mark_sent(db, notification_id, provider_message_id=None) -> None:
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {
            "status": "sent",
            "sent_at": datetime.now(timezone.utc),
            "provider_message_id": provider_message_id,
        }},
    )


def _mark_failed(db, notification_id) -> None:
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {"status": "failed"}},
    )


def _format(n: dict) -> tuple[str, str]:
    """Return (subject, body) for a notification document."""
    subject = n.get("subject")
    body = n.get("body")
    if subject and body:
        return subject, body

    gig_title = n.get("payload", {}).get("gig_title", "a gig")
    templates: dict[str, tuple[str, str]] = {
        "new_gig": (
            "New Gig Matches Your Preferences",
            f"Hi,\n\nA new gig was posted that matches your preferences: '{gig_title}'.\n\n"
            "Log in to GigBoard to apply.\n\nThe GigBoard Team",
        ),
        "new_application": (
            "Someone Applied to Your Gig",
            f"Hi,\n\nSomeone applied to your gig '{gig_title}'.\n\n"
            "Log in to GigBoard to review their application.\n\nThe GigBoard Team",
        ),
        "status_change": (
            "Application Update",
            f"Hi,\n\nThere's been an update on your application for '{gig_title}'.\n\n"
            "Log in to GigBoard for details.\n\nThe GigBoard Team",
        ),
        "weekly_digest": (
            "Your Weekly GigBoard Digest",
            "Hi,\n\nHere's your weekly summary of new gigs on GigBoard.\n\n"
            "Log in to browse and apply.\n\nThe GigBoard Team",
        ),
    }
    return templates.get(n.get("type", ""), ("GigBoard Notification", "You have a new notification."))

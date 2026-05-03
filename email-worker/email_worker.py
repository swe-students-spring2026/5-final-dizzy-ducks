import os
import time
from datetime import datetime, timezone
import sendgrid
from sendgrid.helpers.mail import Mail
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@gigboard.com")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 60))


def get_db(uri=MONGO_URI):
    client = MongoClient(uri)
    return client["gigboard"]


def get_pending_notifications(db):
    now = datetime.now(timezone.utc)
    return list(db.notifications.find({
        "status": "pending",
        "$or": [
            {"scheduled_for": None},
            {"scheduled_for": {"$exists": False}},
            {"scheduled_for": {"$lte": now}},
        ]
    }))


def get_user_email(db, user_id):
    user = db.users.find_one({"_id": user_id}, {"email": 1})
    if user:
        return user.get("email")
    return None


def mark_as_sent(db, notification_id, provider_message_id=None):
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {
            "status": "sent",
            "sent_at": datetime.now(timezone.utc),
            "provider_message_id": provider_message_id,
        }}
    )


def mark_as_failed(db, notification_id):
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {"status": "failed"}}
    )


def send_email(to, subject, body, api_key=SENDGRID_API_KEY):
    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to,
        subject=subject,
        plain_text_content=body
    )
    response = sg.send(message)
    message_id = response.headers.get("X-Message-Id")
    return response.status_code, message_id


def format_notification(n):
    # use subject/body if the Flask app already set them
    subject = n.get("subject")
    body = n.get("body")
    if subject and body:
        return subject, body

    # fallback templates by type
    gig_title = n.get("gig_title", "a gig")
    templates = {
        "new_gig": (
            "New Gig Matches Your Preferences",
            f"Hi,\n\nA new gig was posted that matches your preferences: '{gig_title}'.\n\nLog in to GigBoard to apply.\n\nThe GigBoard Team"
        ),
        "application": (
            "Someone Applied to Your Gig",
            f"Hi,\n\nSomeone applied to your gig '{gig_title}'.\n\nLog in to GigBoard to review their application.\n\nThe GigBoard Team"
        ),
        "status": (
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


def run(db):
    print(f"notification worker started, polling every {POLL_INTERVAL} seconds")
    while True:
        try:
            notifications = get_pending_notifications(db)
            print(f"found {len(notifications)} pending notifications")
            for n in notifications:
                to_email = get_user_email(db, n["user_id"])
                if not to_email:
                    print(f"no email found for user_id {n['user_id']}, skipping")
                    mark_as_failed(db, n["_id"])
                    continue

                subject, body = format_notification(n)
                status_code, message_id = send_email(to_email, subject, body)
                if status_code == 202:
                    mark_as_sent(db, n["_id"], provider_message_id=message_id)
                    print(f"sent '{n.get('type')}' email to {to_email}")
                else:
                    mark_as_failed(db, n["_id"])
                    print(f"failed to send to {to_email}, status: {status_code}")
        except Exception as e:
            print(f"error during poll: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    db = get_db()
    run(db)

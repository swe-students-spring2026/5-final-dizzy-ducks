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
    return list(db.notifications.find({"sent": False}))

def mark_as_sent(db, notification_id):
    db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {
            "sent": True,
            "sent_at": datetime.now(timezone.utc)
        }}
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
    return response.status_code

# --- notification formatter ---
def format_notification(n):
    templates = {
        "application_received": (
            "Someone Applied to Your Gig",
            f"Hi,\n\nSomeone applied to your gig '{n.get('gig_title', 'your gig')}'.\n\nLog in to GigBoard to review their application.\n\nThe GigBoard Team"
        ),
        "application_accepted": (
            "You Got the Gig!",
            f"Hi,\n\nCongratulations! Your application for '{n.get('gig_title', 'a gig')}' was accepted.\n\nLog in to GigBoard for next steps.\n\nThe GigBoard Team"
        ),
        "application_rejected": (
            "Application Update",
            f"Hi,\n\nUnfortunately your application for '{n.get('gig_title', 'a gig')}' was not accepted this time.\n\nKeep browsing GigBoard for more opportunities.\n\nThe GigBoard Team"
        ),
        "new_gig_match": (
            "New Gig Matches Your Preferences",
            f"Hi,\n\nA new gig was posted that matches your preferences: '{n.get('gig_title', 'a gig')}'.\n\nLog in to GigBoard to apply.\n\nThe GigBoard Team"
        ),
    }

    notification_type = n.get("type")
    if notification_type in templates:
        subject, body = templates[notification_type]
        return subject, body

    # fallback to whatever subject/body is already in the document
    return n.get("subject", "GigBoard Notification"), n.get("body", "You have a new notification.")

# --- main loop ---
def run(db):
    print(f"notification worker started, polling every {POLL_INTERVAL} seconds")
    while True:
        try:
            notifications = get_pending_notifications(db)
            print(f"found {len(notifications)} pending notifications")
            for n in notifications:
                subject, body = format_notification(n)
                status = send_email(n["to_email"], subject, body)
                if status == 202:
                    mark_as_sent(db, n["_id"])
                    print(f"sent '{n.get('type')}' email to {n['to_email']}")
                else:
                    print(f"failed to send to {n['to_email']}, status: {status}")
        except Exception as e:
            print(f"error during poll: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    db = get_db()
    run(db)

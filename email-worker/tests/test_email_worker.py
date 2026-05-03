import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from bson import ObjectId

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import email_worker


# --- format_notification ---

def test_format_notification_uses_subject_and_body_from_document():
    n = {"subject": "Custom Subject", "body": "Custom body", "type": "application"}
    subject, body = email_worker.format_notification(n)
    assert subject == "Custom Subject"
    assert body == "Custom body"

def test_format_notification_new_gig_fallback():
    n = {"type": "new_gig", "payload": {"gig_title": "Dog Walking"}}
    subject, body = email_worker.format_notification(n)
    assert subject == "New Gig Matches Your Preferences"
    assert "Dog Walking" in body

def test_format_notification_new_application_fallback():
    n = {"type": "new_application", "payload": {"gig_title": "Tutoring"}}
    subject, body = email_worker.format_notification(n)
    assert subject == "Someone Applied to Your Gig"
    assert "Tutoring" in body

def test_format_notification_status_change_fallback():
    n = {"type": "status_change", "payload": {"gig_title": "Moving Help"}}
    subject, body = email_worker.format_notification(n)
    assert subject == "Application Update"
    assert "Moving Help" in body

def test_format_notification_weekly_digest_fallback():
    n = {"type": "weekly_digest"}
    subject, body = email_worker.format_notification(n)
    assert subject == "Your Weekly GigBoard Digest"
    assert "weekly" in body.lower()

def test_format_notification_missing_gig_title_uses_default():
    n = {"type": "new_application"}
    _, body = email_worker.format_notification(n)
    assert "a gig" in body

def test_format_notification_unknown_type_no_fields():
    n = {"type": "unknown_type"}
    subject, body = email_worker.format_notification(n)
    assert subject == "GigBoard Notification"
    assert body == "You have a new notification."


# --- send_email ---

@patch("email_worker.sendgrid.SendGridAPIClient")
def test_send_email_returns_202_and_message_id(mock_sg_class):
    mock_sg = MagicMock()
    mock_sg.send.return_value.status_code = 202
    mock_sg.send.return_value.headers = {"X-Message-Id": "abc123"}
    mock_sg_class.return_value = mock_sg

    status, message_id = email_worker.send_email("student@nyu.edu", "Subject", "Body", api_key="fake-key")

    assert status == 202
    assert message_id == "abc123"

@patch("email_worker.sendgrid.SendGridAPIClient")
def test_send_email_returns_non_202_on_failure(mock_sg_class):
    mock_sg = MagicMock()
    mock_sg.send.return_value.status_code = 400
    mock_sg.send.return_value.headers = {}
    mock_sg_class.return_value = mock_sg

    status, _ = email_worker.send_email("student@nyu.edu", "Subject", "Body", api_key="fake-key")

    assert status == 400

@patch("email_worker.sendgrid.SendGridAPIClient")
def test_send_email_sends_to_correct_recipient(mock_sg_class):
    mock_sg = MagicMock()
    mock_sg.send.return_value.status_code = 202
    mock_sg.send.return_value.headers = {}
    mock_sg_class.return_value = mock_sg

    email_worker.send_email("recipient@nyu.edu", "Subject", "Body", api_key="fake-key")

    sent_message = mock_sg.send.call_args[0][0]
    assert sent_message.to[0].email == "recipient@nyu.edu"

@patch("email_worker.sendgrid.SendGridAPIClient")
def test_send_email_uses_correct_subject(mock_sg_class):
    mock_sg = MagicMock()
    mock_sg.send.return_value.status_code = 202
    mock_sg.send.return_value.headers = {}
    mock_sg_class.return_value = mock_sg

    email_worker.send_email("student@nyu.edu", "My Subject", "Body", api_key="fake-key")

    sent_message = mock_sg.send.call_args[0][0]
    assert sent_message.subject == "My Subject"


# --- get_pending_notifications ---

def test_get_pending_notifications_queries_pending_status():
    mock_db = MagicMock()
    mock_db.notifications.find.return_value = []

    email_worker.get_pending_notifications(mock_db)

    query = mock_db.notifications.find.call_args[0][0]
    assert query["status"] == "pending"

def test_get_pending_notifications_returns_results():
    mock_db = MagicMock()
    mock_db.notifications.find.return_value = [
        {"_id": ObjectId(), "to_user_id": ObjectId(), "status": "pending"},
        {"_id": ObjectId(), "to_user_id": ObjectId(), "status": "pending"},
    ]

    result = email_worker.get_pending_notifications(mock_db)

    assert len(result) == 2

def test_get_pending_notifications_empty():
    mock_db = MagicMock()
    mock_db.notifications.find.return_value = []

    result = email_worker.get_pending_notifications(mock_db)

    assert result == []


# --- get_user_email ---

def test_get_user_email_returns_email():
    mock_db = MagicMock()
    user_id = ObjectId()
    mock_db.users.find_one.return_value = {"_id": user_id, "email": "student@nyu.edu"}

    result = email_worker.get_user_email(mock_db, user_id)

    assert result == "student@nyu.edu"

def test_get_user_email_returns_none_when_user_not_found():
    mock_db = MagicMock()
    mock_db.users.find_one.return_value = None

    result = email_worker.get_user_email(mock_db, ObjectId())

    assert result is None


# --- mark_as_sent ---

def test_mark_as_sent_sets_status_sent():
    mock_db = MagicMock()
    notification_id = ObjectId()

    email_worker.mark_as_sent(mock_db, notification_id, provider_message_id="msg123")

    call_args = mock_db.notifications.update_one.call_args
    assert call_args[0][0] == {"_id": notification_id}
    assert call_args[0][1]["$set"]["status"] == "sent"

def test_mark_as_sent_stores_provider_message_id():
    mock_db = MagicMock()

    email_worker.mark_as_sent(mock_db, ObjectId(), provider_message_id="msg123")

    call_args = mock_db.notifications.update_one.call_args
    assert call_args[0][1]["$set"]["provider_message_id"] == "msg123"

def test_mark_as_sent_records_utc_timestamp():
    mock_db = MagicMock()

    email_worker.mark_as_sent(mock_db, ObjectId())

    call_args = mock_db.notifications.update_one.call_args
    sent_at = call_args[0][1]["$set"]["sent_at"]
    assert isinstance(sent_at, datetime)
    assert sent_at.tzinfo == timezone.utc


# --- mark_as_failed ---

def test_mark_as_failed_sets_status_failed():
    mock_db = MagicMock()
    notification_id = ObjectId()

    email_worker.mark_as_failed(mock_db, notification_id)

    call_args = mock_db.notifications.update_one.call_args
    assert call_args[0][0] == {"_id": notification_id}
    assert call_args[0][1]["$set"]["status"] == "failed"


# --- run loop ---

@patch("email_worker.time.sleep", return_value=None)
@patch("email_worker.send_email", return_value=(202, "msg123"))
@patch("email_worker.mark_as_sent")
@patch("email_worker.mark_as_failed")
@patch("email_worker.get_user_email", return_value="student@nyu.edu")
@patch("email_worker.get_pending_notifications")
def test_run_sends_and_marks_sent(mock_get, mock_get_email, mock_fail, mock_mark, mock_send, mock_sleep):
    notification_id = ObjectId()
    mock_get.side_effect = [
        [{"_id": notification_id, "to_user_id": ObjectId(), "type": "application", "subject": "S", "body": "B"}],
        Exception("stop loop"),
    ]

    with pytest.raises(Exception, match="stop loop"):
        email_worker.run(MagicMock())

    mock_send.assert_called_once()
    mock_mark.assert_called_once()
    mock_fail.assert_not_called()

@patch("email_worker.time.sleep", return_value=None)
@patch("email_worker.send_email", return_value=(400, None))
@patch("email_worker.mark_as_sent")
@patch("email_worker.mark_as_failed")
@patch("email_worker.get_user_email", return_value="student@nyu.edu")
@patch("email_worker.get_pending_notifications")
def test_run_marks_failed_when_send_fails(mock_get, mock_get_email, mock_fail, mock_mark, mock_send, mock_sleep):
    mock_get.side_effect = [
        [{"_id": ObjectId(), "to_user_id": ObjectId(), "type": "status", "subject": "S", "body": "B"}],
        Exception("stop loop"),
    ]

    with pytest.raises(Exception, match="stop loop"):
        email_worker.run(MagicMock())

    mock_fail.assert_called_once()
    mock_mark.assert_not_called()

@patch("email_worker.time.sleep", return_value=None)
@patch("email_worker.mark_as_failed")
@patch("email_worker.get_user_email", return_value=None)
@patch("email_worker.get_pending_notifications")
def test_run_marks_failed_when_user_email_not_found(mock_get, mock_get_email, mock_fail, mock_sleep):
    mock_get.side_effect = [
        [{"_id": ObjectId(), "to_user_id": ObjectId(), "type": "new_gig", "subject": "S", "body": "B"}],
        Exception("stop loop"),
    ]

    with pytest.raises(Exception, match="stop loop"):
        email_worker.run(MagicMock())

    mock_fail.assert_called_once()

@patch("email_worker.time.sleep", return_value=None)
@patch("email_worker.get_pending_notifications")
def test_run_continues_after_poll_exception(mock_get, mock_sleep):
    mock_get.side_effect = [
        Exception("mongo blip"),
        Exception("stop loop"),
    ]

    with pytest.raises(Exception, match="stop loop"):
        email_worker.run(MagicMock())

    assert mock_get.call_count == 2

@patch("email_worker.time.sleep", return_value=None)
@patch("email_worker.send_email", return_value=(202, "msg"))
@patch("email_worker.mark_as_sent")
@patch("email_worker.mark_as_failed")
@patch("email_worker.get_user_email", return_value="student@nyu.edu")
@patch("email_worker.get_pending_notifications")
def test_run_processes_multiple_notifications(mock_get, mock_get_email, mock_fail, mock_mark, mock_send, mock_sleep):
    mock_get.side_effect = [
        [
            {"_id": ObjectId(), "to_user_id": ObjectId(), "type": "application", "subject": "S1", "body": "B1"},
            {"_id": ObjectId(), "to_user_id": ObjectId(), "type": "new_gig", "subject": "S2", "body": "B2"},
        ],
        Exception("stop loop"),
    ]

    with pytest.raises(Exception, match="stop loop"):
        email_worker.run(MagicMock())

    assert mock_send.call_count == 2
    assert mock_mark.call_count == 2

@patch("email_worker.time.sleep", return_value=None)
@patch("email_worker.send_email", return_value=(202, "msg"))
@patch("email_worker.mark_as_sent")
@patch("email_worker.get_user_email", return_value="student@nyu.edu")
@patch("email_worker.get_pending_notifications")
def test_run_skips_send_when_no_notifications(mock_get, mock_get_email, mock_mark, mock_send, mock_sleep):
    mock_get.side_effect = [
        [],
        Exception("stop loop"),
    ]

    with pytest.raises(Exception, match="stop loop"):
        email_worker.run(MagicMock())

    mock_send.assert_not_called()
    mock_mark.assert_not_called()

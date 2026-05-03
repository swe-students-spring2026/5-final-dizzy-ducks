from __future__ import annotations

from datetime import datetime, timezone


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = str(user_id)


def _seed_mongo_gig(app):
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        poster_id = db.users.insert_one(
            {"name": "Poster", "email": "poster@test.com"}
        ).inserted_id
        applicant_id = db.users.insert_one(
            {"name": "Applicant", "email": "applicant@test.com"}
        ).inserted_id
        gig_id = db.gigs.insert_one(
            {
                "title": "Help set up chairs",
                "category": "event-help",
                "pay": "$45",
                "location": "Student Center",
                "date": "2026-05-20",
                "description": "Set up chairs before an event.",
                "poster_id": poster_id,
                "status": "open",
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id

    return poster_id, applicant_id, gig_id


def test_mongo_gig_detail_shows_apply_form(app, client):
    _, applicant_id, gig_id = _seed_mongo_gig(app)
    _login(client, applicant_id)

    response = client.get(f"/gigs/{gig_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Help set up chairs" in body
    assert "Submit application" in body


def test_mongo_apply_creates_application_and_notification(app, client):
    poster_id, applicant_id, gig_id = _seed_mongo_gig(app)
    _login(client, applicant_id)

    response = client.post(
        f"/gigs/{gig_id}/apply",
        data={"message": "I can be there at 5."},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Application submitted!" in response.get_data(as_text=True)

    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        application = db.applications.find_one(
            {"gig_id": gig_id, "applicant_id": applicant_id}
        )
        assert application is not None
        assert application["status"] == "pending"
        assert application["message"] == "I can be there at 5."

        notification = db.notifications.find_one(
            {"type": "new_application", "to_user_id": poster_id}
        )
        assert notification is not None
        assert notification["status"] == "pending"
        assert notification["payload"]["gig_title"] == "Help set up chairs"


def test_mongo_my_applied_lists_application(app, client):
    _, applicant_id, gig_id = _seed_mongo_gig(app)
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        db.applications.insert_one(
            {
                "gig_id": gig_id,
                "applicant_id": applicant_id,
                "message": "Sounds good.",
                "status": "pending",
                "applied_at": datetime.now(timezone.utc),
            }
        )

    _login(client, applicant_id)
    response = client.get("/my/applied")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Help set up chairs" in body
    assert "Sounds good." in body

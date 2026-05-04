from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId


def _login(client, user_id: ObjectId):
    with client.session_transaction() as sess:
        sess["user_id"] = str(user_id)


def _seed(app):
    """Insert two users and one open gig, return (db, poster_id, applicant_id, gig_id)."""
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
                "title": "Walk my dog",
                "description": "Twice a day, 30 min each.",
                "category": "dog-walking",
                "pay": "$20/hr",
                "poster_id": poster_id,
                "status": "open",
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id
    return poster_id, applicant_id, gig_id


# ---------------------------------------------------------------------------
# Gig detail page — GET /gigs/<id>
# ---------------------------------------------------------------------------

def test_gig_detail_anonymous_can_view(app, client):
    poster_id, _, gig_id = _seed(app)
    res = client.get(f"/gigs/{gig_id}")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Walk my dog" in body
    assert "Twice a day" in body


def test_gig_detail_shows_apply_form_for_non_poster(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    _login(client, applicant_id)
    res = client.get(f"/gigs/{gig_id}")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Apply" in body
    assert "Submit application" in body


def test_gig_detail_poster_sees_their_gig_notice(app, client):
    poster_id, _, gig_id = _seed(app)
    _login(client, poster_id)
    res = client.get(f"/gigs/{gig_id}")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "This is your gig" in body
    assert "Submit application" not in body


def test_gig_detail_shows_existing_application_status(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        db.applications.insert_one(
            {
                "gig_id": gig_id,
                "applicant_id": applicant_id,
                "status": "pending",
                "message": "I love dogs",
                "applied_at": datetime.now(timezone.utc),
            }
        )

    _login(client, applicant_id)
    res = client.get(f"/gigs/{gig_id}")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "pending" in body
    assert "I love dogs" in body
    assert "Submit application" not in body


def test_gig_detail_closed_gig_hides_apply_form(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    with app.app_context():
        from web.app.db import get_db

        get_db().gigs.update_one({"_id": gig_id}, {"$set": {"status": "filled"}})

    _login(client, applicant_id)
    res = client.get(f"/gigs/{gig_id}")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Submit application" not in body
    assert "no longer accepting" in body


def test_gig_detail_invalid_id_returns_404(app, client):
    res = client.get("/gigs/notanid")
    assert res.status_code == 404


def test_gig_detail_missing_gig_returns_404(app, client):
    res = client.get(f"/gigs/{ObjectId()}")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Apply — POST /gigs/<id>/apply
# ---------------------------------------------------------------------------

def test_apply_creates_application_and_queues_notification(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    _login(client, applicant_id)

    res = client.post(
        f"/gigs/{gig_id}/apply",
        data={"message": "I'd love to help!"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "Application submitted" in res.get_data(as_text=True)

    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        app_doc = db.applications.find_one({"gig_id": gig_id, "applicant_id": applicant_id})
        assert app_doc is not None
        assert app_doc["status"] == "pending"
        assert app_doc["message"] == "I'd love to help!"

        note = db.notifications.find_one({"type": "new_application", "to_user_id": poster_id})
        assert note is not None
        assert note["status"] == "pending"


def test_apply_without_message_still_works(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    _login(client, applicant_id)

    res = client.post(f"/gigs/{gig_id}/apply", data={}, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        from web.app.db import get_db

        app_doc = get_db().applications.find_one({"gig_id": gig_id, "applicant_id": applicant_id})
        assert app_doc is not None


def test_apply_duplicate_is_rejected(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    with app.app_context():
        from web.app.db import get_db

        get_db().applications.insert_one(
            {
                "gig_id": gig_id,
                "applicant_id": applicant_id,
                "status": "pending",
                "message": "",
                "applied_at": datetime.now(timezone.utc),
            }
        )

    _login(client, applicant_id)
    res = client.post(f"/gigs/{gig_id}/apply", data={}, follow_redirects=True)
    assert res.status_code == 200
    assert "already applied" in res.get_data(as_text=True)

    with app.app_context():
        from web.app.db import get_db

        count = get_db().applications.count_documents({"gig_id": gig_id})
        assert count == 1


def test_apply_own_gig_is_blocked(app, client):
    poster_id, _, gig_id = _seed(app)
    _login(client, poster_id)

    res = client.post(f"/gigs/{gig_id}/apply", data={}, follow_redirects=True)
    assert res.status_code == 200
    assert "cannot apply to your own" in res.get_data(as_text=True)

    with app.app_context():
        from web.app.db import get_db

        count = get_db().applications.count_documents({"gig_id": gig_id})
        assert count == 0


def test_apply_to_filled_gig_is_blocked(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    with app.app_context():
        from web.app.db import get_db

        get_db().gigs.update_one({"_id": gig_id}, {"$set": {"status": "filled"}})

    _login(client, applicant_id)
    res = client.post(f"/gigs/{gig_id}/apply", data={}, follow_redirects=True)
    assert res.status_code == 200
    assert "no longer accepting" in res.get_data(as_text=True)

    with app.app_context():
        from web.app.db import get_db

        count = get_db().applications.count_documents({"gig_id": gig_id})
        assert count == 0


def test_apply_requires_login(app, client):
    _, _, gig_id = _seed(app)
    res = client.post(f"/gigs/{gig_id}/apply", data={})
    assert res.status_code in (302, 401)


# ---------------------------------------------------------------------------
# My applications tracker — GET /my/applied
# ---------------------------------------------------------------------------

def test_my_applied_shows_only_users_applications(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    other_id = None
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        other_id = db.users.insert_one({"name": "Other", "email": "other@test.com"}).inserted_id
        other_gig_id = db.gigs.insert_one(
            {
                "title": "Other gig",
                "poster_id": other_id,
                "status": "open",
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id
        db.applications.insert_many(
            [
                {
                    "gig_id": gig_id,
                    "applicant_id": applicant_id,
                    "status": "pending",
                    "message": "",
                    "applied_at": datetime.now(timezone.utc),
                },
                {
                    "gig_id": other_gig_id,
                    "applicant_id": other_id,
                    "status": "accepted",
                    "message": "",
                    "applied_at": datetime.now(timezone.utc),
                },
            ]
        )

    _login(client, applicant_id)
    res = client.get("/my/applied")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Walk my dog" in body
    assert "Other gig" not in body


def test_my_applied_shows_application_status(app, client):
    poster_id, applicant_id, gig_id = _seed(app)
    with app.app_context():
        from web.app.db import get_db

        get_db().applications.insert_one(
            {
                "gig_id": gig_id,
                "applicant_id": applicant_id,
                "status": "accepted",
                "message": "",
                "applied_at": datetime.now(timezone.utc),
            }
        )

    _login(client, applicant_id)
    res = client.get("/my/applied")
    body = res.get_data(as_text=True)
    assert "accepted" in body


def test_my_applied_empty_state(app, client):
    poster_id, applicant_id, _ = _seed(app)
    _login(client, applicant_id)
    res = client.get("/my/applied")
    assert res.status_code == 200
    assert "No applications yet" in res.get_data(as_text=True)


def test_my_applied_requires_login(app, client):
    res = client.get("/my/applied")
    assert res.status_code in (302, 401)

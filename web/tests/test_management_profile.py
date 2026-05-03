from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

VALID_GIG = {
    "title": "Post flyers",
    "category": "event-help",
    "pay": "$30",
    "location": "Main Quad",
    "date": "2026-05-16",
    "description": "Put up event flyers on approved campus boards.",
}


def _login(client, user_id: ObjectId):
    with client.session_transaction() as sess:
        sess["user_id"] = str(user_id)


def test_my_gigs_lists_only_my_posts(app, client):
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        me = db.users.insert_one({"name": "Me", "email": "me@test.com"}).inserted_id
        other = db.users.insert_one(
            {"name": "Other", "email": "o@test.com"}
        ).inserted_id
        db.gigs.insert_many(
            [
                {
                    "title": "My gig",
                    "category": "tutoring",
                    "poster_id": me,
                    "status": "open",
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "title": "Not mine",
                    "category": "moving",
                    "poster_id": other,
                    "status": "open",
                    "created_at": datetime.now(timezone.utc),
                },
            ]
        )

    _login(client, me)
    res = client.get("/my/gigs")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "My gig" in body
    assert "Not mine" not in body


def test_mongo_user_can_post_gig(app, client):
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        poster_id = db.users.insert_one(
            {"name": "Poster", "email": "poster@test.com"}
        ).inserted_id

    _login(client, poster_id)

    res = client.post("/my/gigs/new", data=VALID_GIG, follow_redirects=True)
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Gig posted." in body
    assert "Post flyers" in body

    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        gig = db.gigs.find_one({"title": "Post flyers"})
        assert gig is not None
        assert gig["poster_id"] == poster_id
        assert gig["status"] == "open"
        assert isinstance(gig["created_at"], datetime)


def test_poster_can_accept_and_queues_notification(app, client):
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        poster_id = db.users.insert_one(
            {"name": "Poster", "email": "p@test.com"}
        ).inserted_id
        applicant_id = db.users.insert_one(
            {
                "name": "Applicant",
                "email": "a@test.com",
                "rating_avg": 4.8,
                "rating_count": 12,
                "jobs_completed": 3,
            }
        ).inserted_id
        gig_id = db.gigs.insert_one(
            {
                "title": "Help me move",
                "category": "moving",
                "poster_id": poster_id,
                "status": "open",
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id
        app_id = db.applications.insert_one(
            {
                "gig_id": gig_id,
                "applicant_id": applicant_id,
                "message": "I can help!",
                "status": "pending",
                "applied_at": datetime.now(timezone.utc),
            }
        ).inserted_id

    _login(client, poster_id)

    res = client.post(
        f"/my/gigs/{gig_id}/applications/{app_id}/decision",
        data={"action": "accept"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Applicant accepted" in body

    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        updated_app = db.applications.find_one({"_id": app_id})
        assert updated_app["status"] == "accepted"

        gig = db.gigs.find_one({"_id": gig_id})
        assert gig["status"] == "filled"

        note = db.notifications.find_one(
            {"type": "status_change", "to_user_id": applicant_id}
        )
        assert note is not None
        assert note["status"] == "pending"
        assert note["payload"]["new_status"] == "accepted"


def test_profile_update_tags(app, client):
    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        me = db.users.insert_one(
            {"name": "Me", "email": "me@test.com", "tags": ["tutoring"]}
        ).inserted_id

    _login(client, me)
    res = client.post(
        "/me",
        data={"name": "Me2", "tags": "moving, tutoring, , dog-walking"},
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        from web.app.db import get_db

        db = get_db()
        user = db.users.find_one({"_id": me})
        assert user["name"] == "Me2"
        assert user["tags"] == ["moving", "tutoring", "dog-walking"]

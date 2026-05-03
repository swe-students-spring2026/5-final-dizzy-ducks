import mongomock
import pytest

from web import create_app
from web.repositories import DuplicateEmailError, InMemoryRepository, MongoRepository


def test_create_app_builds_in_memory_repository_by_default():
    app = create_app({"SECRET_KEY": "test-secret", "TESTING": True})

    assert isinstance(app.repository, InMemoryRepository)
    assert len(app.repository.list_open_gigs()) == 6


def test_create_app_can_disable_sample_gigs():
    app = create_app(
        {"SECRET_KEY": "test-secret", "SEED_SAMPLE_GIGS": False, "TESTING": True}
    )

    assert app.repository.list_open_gigs() == []


def test_in_memory_repository_filters_open_gigs_by_tags_and_search(repository):
    repository.create_gig(
        title="Move a couch",
        category="delivery",
        pay="$40",
        location="Campus",
        date="2026-05-01",
        description="Need a pickup truck.",
        poster_id="1",
    )
    repository.create_gig(
        title="Algebra review",
        category="tutoring",
        pay="$25/hr",
        location="Library",
        date="2026-05-02",
        description="Help with linear equations.",
        poster_id="1",
    )
    repository.create_gig(
        title="Filled delivery",
        category="delivery",
        pay="$15",
        location="Campus",
        date="2026-05-03",
        description="Already assigned.",
        poster_id="1",
        status="filled",
    )

    delivery_gigs = repository.list_open_gigs(tags=["delivery"])
    assert [gig["title"] for gig in delivery_gigs] == ["Move a couch"]

    searched_gigs = repository.list_open_gigs(search="linear")
    assert [gig["title"] for gig in searched_gigs] == ["Algebra review"]


def test_in_memory_repository_updates_profile_and_lists_poster_gigs(repository):
    user = repository.create_user(
        name="Casey Helper",
        email="casey@example.com",
        password_hash="hashed-password",
    )
    repository.create_gig(
        title="Mine",
        category="delivery",
        pay="$30",
        location="Campus",
        date="2026-05-07",
        description="A posted gig.",
        poster_id=user["id"],
    )
    repository.create_gig(
        title="Someone else's",
        category="tutoring",
        pay="$30",
        location="Library",
        date="2026-05-07",
        description="Another posted gig.",
        poster_id="other-user",
    )

    updated = repository.update_user_profile(
        user["id"], name="Casey Poster", tags=["delivery", "bad-tag"]
    )

    assert updated["name"] == "Casey Poster"
    assert updated["tags"] == ["delivery"]
    assert updated["notification_preferences"]["tags"] == ["delivery"]
    assert [gig["title"] for gig in repository.list_gigs_by_poster(user["id"])] == [
        "Mine"
    ]


def test_mongo_repository_handles_users_and_tags():
    repository = MongoRepository(client=mongomock.MongoClient(), db_name="test")

    user = repository.create_user(
        name="Taylor Poster",
        email="TAYLOR@example.com",
        password_hash="hashed-password",
    )

    assert repository.get_user_by_email("taylor@example.com")["id"] == user["id"]
    assert repository.get_user_by_id(user["id"])["email"] == "taylor@example.com"

    updated = repository.update_user_tags(user["id"], ["delivery", "bad-tag"])
    assert updated["notification_preferences"]["tags"] == ["delivery"]


def test_mongo_repository_rejects_duplicate_email():
    repository = MongoRepository(client=mongomock.MongoClient(), db_name="test")
    repository.create_user(
        name="Taylor Poster",
        email="taylor@example.com",
        password_hash="hashed-password",
    )

    with pytest.raises(DuplicateEmailError):
        repository.create_user(
            name="Taylor Poster",
            email="TAYLOR@example.com",
            password_hash="hashed-password",
        )


def test_mongo_repository_returns_none_for_invalid_user_id():
    repository = MongoRepository(client=mongomock.MongoClient(), db_name="test")

    assert repository.get_user_by_id("not-an-object-id") is None
    assert repository.update_user_tags("not-an-object-id", ["delivery"]) is None


def test_mongo_repository_filters_open_gigs_by_tags_and_search():
    repository = MongoRepository(client=mongomock.MongoClient(), db_name="test")
    repository.create_gig(
        title="Network setup",
        category="tech-support",
        pay="$60",
        location="Dorm",
        date="2026-05-04",
        description="Set up a router.",
        poster_id="1",
    )
    repository.create_gig(
        title="Dog walk",
        category="pet-care",
        pay="$20",
        location="Park",
        date="2026-05-05",
        description="Evening walk.",
        poster_id="1",
    )
    repository.create_gig(
        title="Old laptop help",
        category="tech-support",
        pay="$30",
        location="Dorm",
        date="2026-05-06",
        description="This one is no longer open.",
        poster_id="1",
        status="filled",
    )

    tech_gigs = repository.list_open_gigs(tags=["tech-support"])
    assert [gig["title"] for gig in tech_gigs] == ["Network setup"]

    searched_gigs = repository.list_open_gigs(search="evening")
    assert [gig["title"] for gig in searched_gigs] == ["Dog walk"]


def test_mongo_repository_updates_profile_and_lists_poster_gigs():
    repository = MongoRepository(client=mongomock.MongoClient(), db_name="test")
    user = repository.create_user(
        name="Taylor Poster",
        email="poster@example.com",
        password_hash="hashed-password",
    )
    repository.create_gig(
        title="Posted by Taylor",
        category="delivery",
        pay="$45",
        location="Campus",
        date="2026-05-08",
        description="Carry boxes.",
        poster_id=user["id"],
    )

    updated = repository.update_user_profile(
        user["id"], name="Taylor Updated", tags=["delivery", "unknown"]
    )

    assert updated["name"] == "Taylor Updated"
    assert updated["tags"] == ["delivery"]
    assert updated["notification_preferences"]["tags"] == ["delivery"]
    assert [gig["title"] for gig in repository.list_gigs_by_poster(user["id"])] == [
        "Posted by Taylor"
    ]

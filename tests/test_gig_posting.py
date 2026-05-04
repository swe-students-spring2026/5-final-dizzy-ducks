VALID_GIG = {
    "title": "Load band gear",
    "category": "event-help",
    "pay": "$50",
    "location": "Student Center",
    "date": "2026-05-15",
    "description": "Carry instruments and amps from the curb to the auditorium.",
}


def _signup(client, repository):
    client.post(
        "/signup",
        data={
            "name": "Taylor Poster",
            "email": "taylor@example.com",
            "password": "password123",
        },
    )
    return repository.get_user_by_email("taylor@example.com")


def test_new_gig_requires_login(client):
    response = client.get("/my/gigs/new")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_new_gig_form_renders_category_options(client, repository):
    _signup(client, repository)

    response = client.get("/my/gigs/new")

    assert response.status_code == 200
    assert b"Post a gig" in response.data
    assert b'value="event-help"' in response.data
    assert b"Event help" in response.data


def test_in_memory_user_can_post_gig(client, repository):
    user = _signup(client, repository)

    response = client.post("/my/gigs/new", data=VALID_GIG, follow_redirects=True)

    assert response.status_code == 200
    assert b"Gig posted." in response.data
    assert b"Load band gear" in response.data

    posted = repository.list_gigs_by_poster(user["id"])
    assert len(posted) == 1
    assert posted[0]["title"] == "Load band gear"
    assert posted[0]["category"] == "event-help"
    assert posted[0]["status"] == "open"


def test_new_gig_validation_preserves_values_and_does_not_create_gig(
    client, repository
):
    user = _signup(client, repository)

    invalid = {
        **VALID_GIG,
        "title": "",
        "category": "not-a-category",
        "date": "05/15/2026",
    }
    response = client.post("/my/gigs/new", data=invalid)

    assert response.status_code == 200
    assert b"Title is required." in response.data
    assert b"Choose a valid category." in response.data
    assert b"Date must use YYYY-MM-DD format." in response.data
    assert b'value="Student Center"' in response.data
    assert repository.list_gigs_by_poster(user["id"]) == []


def test_new_gig_requires_zero_padded_date(client, repository):
    user = _signup(client, repository)
    invalid = {**VALID_GIG, "date": "2026-5-15"}

    response = client.post("/my/gigs/new", data=invalid)

    assert response.status_code == 200
    assert b"Date must use YYYY-MM-DD format." in response.data
    assert repository.list_gigs_by_poster(user["id"]) == []

def _signup_and_onboard(client, tags=("delivery",)):
    client.post(
        "/signup",
        data={
            "name": "Jamie Seeker",
            "email": "jamie@example.com",
            "password": "password123",
        },
    )
    client.post("/onboarding", data={"tags": list(tags)})


def _seed_gigs(repository):
    repository.create_gig(
        title="Move boxes",
        category="delivery",
        pay="$35",
        location="North Campus",
        date="2026-05-10",
        description="Carry boxes from a dorm to storage.",
        poster_id="poster-1",
    )
    repository.create_gig(
        title="Calculus review",
        category="tutoring",
        pay="$25/hr",
        location="Library",
        date="2026-05-11",
        description="Work through practice derivatives.",
        poster_id="poster-2",
    )
    repository.create_gig(
        title="Old delivery job",
        category="delivery",
        pay="$20",
        location="South Campus",
        date="2026-05-12",
        description="This should not show because it is filled.",
        poster_id="poster-3",
        status="filled",
    )


def test_dashboard_requires_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/"


def test_dashboard_uses_saved_tags_by_default(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("delivery",))

    response = client.get("/")

    assert response.status_code == 200
    assert b"Move boxes" in response.data
    assert b"Calculus review" not in response.data
    assert b"Old delivery job" not in response.data
    assert b"1 open gig" in response.data


def test_dashboard_query_tags_override_saved_tags(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("delivery",))

    response = client.get("/", query_string=[("tag", "tutoring")])

    assert response.status_code == 200
    assert b"Calculus review" in response.data
    assert b"Move boxes" not in response.data


def test_dashboard_search_filters_matching_gigs(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("delivery", "tutoring"))

    response = client.get(
        "/",
        query_string=[("tag", "delivery"), ("tag", "tutoring"), ("q", "derivatives")],
    )

    assert response.status_code == 200
    assert b"Calculus review" in response.data
    assert b"Move boxes" not in response.data


def test_dashboard_empty_state(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("pet-care",))

    response = client.get("/")

    assert response.status_code == 200
    assert b"No open gigs match your filters." in response.data

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


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = str(user_id)


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
    assert b'href="/gigs/1"' in response.data
    assert b"View &amp; apply" in response.data


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
        query_string=[("tag", "tutoring"), ("q", "derivatives")],
    )

    assert response.status_code == 200
    assert b"Calculus review" in response.data
    assert b"Move boxes" not in response.data


def test_dashboard_empty_state(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("pet-care",))

    response = client.get("/")

    assert response.status_code == 200
    assert b"No gigs match your filters" in response.data


def test_my_applications_page_handles_repository_user(client, repository):
    _signup_and_onboard(client, tags=("delivery",))

    response = client.get("/my/applied")

    assert response.status_code == 200
    assert b"My applications" in response.data
    assert b"No applications yet" in response.data


def test_dashboard_apply_button_creates_repository_application(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("delivery",))

    response = client.post("/gigs/1/apply", follow_redirects=True)

    assert response.status_code == 200
    assert b"Application submitted!" in response.data
    assert b"Move boxes" in response.data
    assert b"pending" in response.data


def test_repository_gig_detail_shows_existing_application(client, repository):
    _seed_gigs(repository)
    _signup_and_onboard(client, tags=("delivery",))
    client.post("/gigs/1/apply")

    response = client.get("/gigs/1")

    assert response.status_code == 200
    assert b"Move boxes" in response.data
    assert b"Your application" in response.data


def test_repository_view_applicants_lists_applicant(client, repository):
    poster = repository.create_user(
        name="Poster",
        email="poster@example.com",
        password_hash="hash",
    )
    applicant = repository.create_user(
        name="Applicant",
        email="applicant@example.com",
        password_hash="hash",
    )
    gig = repository.create_gig(
        title="Set up chairs",
        category="event-help",
        pay="$40",
        location="Student Center",
        date="2026-05-20",
        description="Set up chairs for an event.",
        poster_id=poster["id"],
    )
    repository.create_application(
        gig_id=gig["id"],
        applicant_id=applicant["id"],
        message="I can help.",
    )
    _login(client, poster["id"])

    response = client.get(f"/my/gigs/{gig['id']}")

    assert response.status_code == 200
    assert b"Applicants" in response.data
    assert b"Applicant" in response.data
    assert b"I can help." in response.data
    assert b"Accept" in response.data


def test_repository_poster_can_accept_application(client, repository):
    poster = repository.create_user(
        name="Poster",
        email="poster@example.com",
        password_hash="hash",
    )
    applicant = repository.create_user(
        name="Applicant",
        email="applicant@example.com",
        password_hash="hash",
    )
    gig = repository.create_gig(
        title="Set up chairs",
        category="event-help",
        pay="$40",
        location="Student Center",
        date="2026-05-20",
        description="Set up chairs for an event.",
        poster_id=poster["id"],
    )
    application = repository.create_application(
        gig_id=gig["id"],
        applicant_id=applicant["id"],
        message="I can help.",
    )
    _login(client, poster["id"])

    response = client.post(
        f"/my/gigs/{gig['id']}/applications/{application['id']}/decision",
        data={"action": "accept"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Applicant accepted" in response.data
    assert repository.get_application_by_id(application["id"])["status"] == "accepted"
    assert repository.get_gig_by_id(gig["id"])["status"] == "filled"

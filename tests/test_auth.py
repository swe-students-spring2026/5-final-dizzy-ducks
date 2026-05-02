from werkzeug.security import check_password_hash


def test_signup_creates_user_and_redirects_to_onboarding(client, repository):
    response = client.post(
        "/signup",
        data={
            "name": "Alex Driver",
            "email": "ALEX@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/onboarding"

    user = repository.get_user_by_email("alex@example.com")
    assert user["name"] == "Alex Driver"
    assert user["email"] == "alex@example.com"
    assert check_password_hash(user["password_hash"], "password123")
    assert user["password_hash"] != "password123"

    with client.session_transaction() as session:
        assert session["user_id"] == user["id"]


def test_signup_validates_required_fields(client):
    response = client.post(
        "/signup",
        data={"name": "", "email": "bad-email", "password": "short"},
    )

    assert response.status_code == 200
    assert b"Name is required." in response.data
    assert b"Enter a valid email address." in response.data
    assert b"Password must be at least 8 characters." in response.data


def test_signup_rejects_duplicate_email(client):
    data = {
        "name": "Alex Driver",
        "email": "alex@example.com",
        "password": "password123",
    }
    client.post("/signup", data=data)
    response = client.post("/signup", data=data)

    assert response.status_code == 200
    assert b"An account with that email already exists." in response.data


def test_login_and_logout(client):
    client.post(
        "/signup",
        data={
            "name": "Morgan Tutor",
            "email": "morgan@example.com",
            "password": "password123",
        },
    )
    client.post("/logout")

    response = client.post(
        "/login",
        data={"email": "morgan@example.com", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

    response = client.post("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"

    with client.session_transaction() as session:
        assert "user_id" not in session


def test_login_rejects_bad_credentials(client):
    response = client.post(
        "/login",
        data={"email": "missing@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_protected_routes_redirect_to_login(client):
    response = client.get("/onboarding")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/onboarding"


def test_login_ignores_external_next_url(client):
    client.post(
        "/signup",
        data={
            "name": "Morgan Tutor",
            "email": "morgan@example.com",
            "password": "password123",
        },
    )
    client.post("/logout")

    response = client.post(
        "/login?next=https://example.com",
        data={"email": "morgan@example.com", "password": "password123"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"

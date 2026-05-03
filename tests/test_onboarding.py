import re


def _signup(client):
    client.post(
        "/signup",
        data={
            "name": "Sam Helper",
            "email": "sam@example.com",
            "password": "password123",
        },
    )


def test_onboarding_saves_known_tags(client, repository):
    _signup(client)

    response = client.post(
        "/onboarding",
        data={"tags": ["delivery", "yard-work", "unknown"]},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    user = repository.get_user_by_email("sam@example.com")
    assert user["notification_preferences"]["tags"] == ["delivery", "yard-work"]


def test_onboarding_requires_at_least_one_valid_tag(client):
    _signup(client)

    response = client.post("/onboarding", data={"tags": ["unknown"]})

    assert response.status_code == 200
    assert b"Choose at least one job tag." in response.data


def test_onboarding_checks_previously_saved_tags(client, repository):
    _signup(client)
    user = repository.get_user_by_email("sam@example.com")
    repository.update_user_tags(user["id"], ["tutoring"])

    response = client.get("/onboarding")

    assert response.status_code == 200
    assert re.search(rb'value="tutoring"\s[^>]*\bselected\b', response.data)

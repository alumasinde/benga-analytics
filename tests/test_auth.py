def signup_payload(**overrides):
    payload = {
        "first_name": "Albert",
        "last_name": "Masinde",
        "email": "tester@example.com",
        "password": "strong-password",
        "confirm_password": "strong-password",
        "accepted_terms": True,
    }
    payload.update(overrides)
    return payload


def test_signup_login_logout_flow(client):
    response = client.post("/api/auth/signup", json=signup_payload())
    assert response.status_code == 201

    user = response.get_json()["user"]
    assert user["first_name"] == "Albert"
    assert user["last_name"] == "Masinde"
    assert user["display_name"] == "Albert Masinde"

    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_weak_password_rejected(client):
    response = client.post(
        "/api/auth/signup",
        json=signup_payload(password="short", confirm_password="short"),
    )
    assert response.status_code == 400


def test_password_confirmation_is_required(client):
    response = client.post(
        "/api/auth/signup",
        json=signup_payload(confirm_password="different-password"),
    )
    assert response.status_code == 400
    assert "match" in response.get_json()["error"].lower()


def test_terms_acceptance_is_required(client):
    response = client.post(
        "/api/auth/signup",
        json=signup_payload(accepted_terms=False),
    )
    assert response.status_code == 400
    assert "terms" in response.get_json()["error"].lower()

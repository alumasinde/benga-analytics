def test_signup_returns_public_user_with_free_plan(client):
    response = client.post(
        "/api/auth/signup",
        json={"email": "free@example.com", "password": "strong-password"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    user = payload["user"]

    assert user["tier"] == "free"
    assert user["plan"]["name"] == "Free"
    assert user["plan"]["limits"]["max_rows_per_dataset"] == 50000
    assert "password_hash" not in user


def test_plans_endpoint_is_public_and_dynamic(client):
    response = client.get("/api/plans")

    assert response.status_code == 200
    plans = response.get_json()["plans"]
    assert "free" in plans
    assert "enterprise_pro" in plans
    assert plans["free"]["features"]["csv_upload"] is True

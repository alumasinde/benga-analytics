def test_signup_login_logout_flow(client):
    response = client.post("/api/auth/signup", json={"email": "tester@example.com", "password": "strong-password"})
    assert response.status_code == 201
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401

def test_weak_password_rejected(client):
    response = client.post("/api/auth/signup", json={"email": "weak@example.com", "password": "short"})
    assert response.status_code == 400

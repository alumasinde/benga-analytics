def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "BengaAnalytics" in response.text

def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"BengaAnalytics" in response.data


def test_legal_pages_load(client):
    assert client.get("/terms").status_code == 200
    assert client.get("/privacy").status_code == 200

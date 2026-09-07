import io

def signup(client):
    return client.post("/api/auth/signup", json={"email": "upload@example.com", "password": "strong-password"})

def test_upload_rejects_unsupported_extension(client):
    signup(client)
    response = client.post("/api/upload", data={"file": (io.BytesIO(b"hello"), "notes.txt")}, content_type="multipart/form-data")
    assert response.status_code == 400

def test_upload_creates_dynamic_metadata_and_records(client):
    signup(client)
    response = client.post("/api/upload", data={"file": (io.BytesIO(b"Region,Revenue\nNairobi,100\nMombasa,200\n"), "sales.csv")}, content_type="multipart/form-data")
    assert response.status_code == 201
    payload = response.get_json()
    assert "Region" in payload["metadata"]["dimensions"]
    assert "Revenue" in payload["metadata"]["metrics"]
    assert payload["metadata"]["row_count"] == 2

import io


def signup(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "first_name": "Upload",
            "last_name": "Tester",
            "email": "upload@example.com",
            "password": "strong-password",
            "confirm_password": "strong-password",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 201, response.get_json()
    return response


def test_upload_rejects_unsupported_extension(client):
    signup(client)
    response = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"hello"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "CSV and XLSX" in response.get_json()["error"]


def test_upload_creates_dynamic_metadata_and_records(client):
    signup(client)
    response = client.post(
        "/api/upload",
        data={
            "file": (
                io.BytesIO(b"Region,Revenue\nNairobi,100\nMombasa,200\n"),
                "sales.csv",
            )
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()

    payload = response.get_json()
    assert "Region" in payload["metadata"]["dimensions"]
    assert "Revenue" in payload["metadata"]["metrics"]
    assert payload["metadata"]["row_count"] == 2

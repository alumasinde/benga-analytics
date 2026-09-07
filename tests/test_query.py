import io


def setup_dataset(client):
    signup = client.post(
        "/api/auth/signup",
        json={
            "first_name": "Query",
            "last_name": "Tester",
            "email": "query@example.com",
            "password": "strong-password",
            "confirm_password": "strong-password",
            "accepted_terms": True,
        },
    )
    assert signup.status_code == 201, signup.get_json()

    response = client.post(
        "/api/upload",
        data={
            "file": (
                io.BytesIO(
                    b"Region,Revenue,Product\n"
                    b"Nairobi,100,Laptop\n"
                    b"Nairobi,50,Phone\n"
                    b"Mombasa,200,Laptop\n"
                ),
                "data.csv",
            )
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["dataset"]["_id"]


def test_dynamic_sum_query(client):
    dataset_id = setup_dataset(client)
    response = client.post(
        "/api/query",
        json={
            "dataset_id": dataset_id,
            "aggregation": "sum",
            "metric": "Revenue",
            "group_by": "Region",
        },
    )
    assert response.status_code == 200
    rows = response.get_json()["rows"]
    assert {row["label"]: row["value"] for row in rows} == {
        "Mombasa": 200,
        "Nairobi": 150,
    }


def test_invalid_metric_is_rejected(client):
    dataset_id = setup_dataset(client)
    response = client.post(
        "/api/query",
        json={
            "dataset_id": dataset_id,
            "aggregation": "sum",
            "metric": "NotAColumn",
            "group_by": "Region",
        },
    )
    assert response.status_code == 400

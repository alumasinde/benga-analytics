import io

def setup_dataset(client):
    client.post("/api/auth/signup", json={"email": "query@example.com", "password": "strong-password"})
    response = client.post("/api/upload", data={"file": (io.BytesIO(b"Region,Revenue,Product\nNairobi,100,Laptop\nNairobi,50,Phone\nMombasa,200,Laptop\n"), "data.csv")}, content_type="multipart/form-data")
    return response.get_json()["dataset"]["_id"]

def test_dynamic_sum_query(client):
    dataset_id = setup_dataset(client)
    response = client.post("/api/query", json={"dataset_id": dataset_id, "aggregation": "sum", "metric": "Revenue", "group_by": "Region"})
    assert response.status_code == 200
    rows = response.get_json()["rows"]
    assert {r["label"]: r["value"] for r in rows} == {"Mombasa": 200, "Nairobi": 150}

def test_invalid_metric_is_rejected(client):
    dataset_id = setup_dataset(client)
    response = client.post("/api/query", json={"dataset_id": dataset_id, "aggregation": "sum", "metric": "NotAColumn", "group_by": "Region"})
    assert response.status_code == 400

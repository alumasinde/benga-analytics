from services.auth_service import AuthService
from services.dataset_service import DatasetService
from services.query_service import QueryService


def signup_payload(email="service@example.com"):
    return {"first_name":"Service","last_name":"Tester","email":email,"password":"strong-password","confirm_password":"strong-password","accepted_terms":True}


def test_auth_service_creates_and_authenticates_user(test_database):
    service = AuthService(test_database)
    user = service.signup(signup_payload())
    assert user["email"] == "service@example.com"
    assert service.authenticate("service@example.com", "strong-password")["id"] == user["id"]
    assert service.authenticate("service@example.com", "wrong") is None


def test_dataset_and_query_services_work_together(test_database, sample_csv_file):
    user = AuthService(test_database).signup(signup_payload("analytics@example.com"))
    dataset, metadata = DatasetService(test_database).ingest(user, sample_csv_file)
    assert metadata["row_count"] == 3
    result = QueryService(test_database).execute(dataset=dataset, dataset_id=dataset["id"], tenant_id=user["tenant_id"], payload={"aggregation":"sum","metric":"Revenue","group_by":"Region"})
    assert {row["label"]: row["value"] for row in result["rows"]} == {"Mombasa": 200.0, "Nairobi": 150.0}

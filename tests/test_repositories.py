from database.repositories import DatasetRepository, RecordRepository, UserRepository
from services.auth_service import AuthService


def test_repositories_are_available(test_database):
    assert UserRepository(test_database).engine is test_database.engine
    assert DatasetRepository(test_database).engine is test_database.engine
    assert RecordRepository(test_database).engine is test_database.engine


def test_dataset_repository_is_tenant_scoped(test_database):
    user = AuthService(test_database).signup({"first_name":"Repo","last_name":"User","email":"repo@example.com","password":"strong-password","confirm_password":"strong-password","accepted_terms":True})
    assert DatasetRepository(test_database).count_for_tenant(user["tenant_id"]) == 0

import pytest
import mongomock
import database
from app import app

@pytest.fixture()
def client():
    fake_client = mongomock.MongoClient()
    fake_db = fake_client["benga_test"]
    database.db.client = fake_client
    database.db.db = fake_db
    database.db.users = fake_db.users
    database.db.datasets = fake_db.datasets
    database.db.records = fake_db.records
    database.db.usage = fake_db.usage
    database.db.saved_queries = fake_db.saved_queries
    database.db.audit_logs = fake_db.audit_logs
    app.config.update(TESTING=True, SECRET_KEY="test-secret", SESSION_COOKIE_SECURE=False)
    with app.test_client() as c:
        yield c

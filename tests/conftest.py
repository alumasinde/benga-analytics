import mongomock
import pytest

from app import app
from database import Database


@pytest.fixture()
def client(monkeypatch):
    """Create a fresh isolated application database for every test."""
    test_database = Database(
        client=mongomock.MongoClient(),
        db_name="benga_test",
        ensure_indexes=True,
    )

    import app as app_module
    monkeypatch.setattr(app_module, "db", test_database)

    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        SESSION_COOKIE_SECURE=False,
    )

    with app.test_client() as test_client:
        yield test_client

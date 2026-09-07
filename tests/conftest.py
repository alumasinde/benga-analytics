import pytest

from app import app
from database import Database


@pytest.fixture()
def client(monkeypatch):
    test_database = Database(
        database_url="sqlite+pysqlite:///:memory:",
        ensure_schema=True,
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

    test_database.close()

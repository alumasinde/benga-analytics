import mongomock
import pytest

from database import Database


def test_legacy_non_unique_tenant_index_is_reconciled():
    client = mongomock.MongoClient()
    database = Database(client=client, db_name="legacy_index_test")

    database.users.create_index([("tenant_id", 1)], name="tenant_id_1")
    database.ensure_indexes()

    indexes = {index["name"]: index for index in database.users.list_indexes()}
    assert indexes["users_tenant_id_unique"]["unique"] is True
    assert "tenant_id_1" not in indexes


def test_duplicate_legacy_values_are_reported_before_unique_upgrade():
    client = mongomock.MongoClient()
    database = Database(client=client, db_name="duplicate_index_test")

    # Simulate an old, non-unique tenant index. Data must be inserted before the
    # index is created because a unique index would reject the duplicate fixture.
    database.users.insert_many([
        {"tenant_id": "duplicate-tenant"},
        {"tenant_id": "duplicate-tenant"},
    ])
    database.users.create_index([("tenant_id", 1)], name="tenant_id_1", unique=False)

    with pytest.raises(RuntimeError, match="duplicate"):
        database.ensure_indexes()

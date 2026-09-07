from sqlalchemy import inspect

from database import Database


def test_relational_schema_has_required_indexes():
    database = Database(
        database_url="sqlite+pysqlite:///:memory:",
        ensure_schema=True,
    )

    inspector = inspect(database.engine)
    datasets = {index["name"] for index in inspector.get_indexes("datasets")}
    records = {index["name"] for index in inspector.get_indexes("records")}

    assert "ix_datasets_tenant_created" in datasets
    assert "ix_datasets_owner_created" in datasets
    assert "ix_records_dataset_tenant" in records

    database.close()

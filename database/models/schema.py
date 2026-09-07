from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Table

from database.base import metadata

users = Table(
    "users", metadata,
    Column("id", String(36), primary_key=True),
    Column("tenant_id", String(36), nullable=False, unique=True),
    Column("first_name", String(80), nullable=False),
    Column("last_name", String(80), nullable=False),
    Column("email", String(255), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("tier", String(50), nullable=False),
    Column("subscription", JSON, nullable=False),
    Column("terms", JSON, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

datasets = Table(
    "datasets", metadata,
    Column("id", String(36), primary_key=True),
    Column("tenant_id", String(36), nullable=False),
    Column("owner_id", String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("status", String(30), nullable=False),
    Column("schema_metadata", JSON, nullable=False),
    Column("row_count", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_datasets_tenant_created", "tenant_id", "created_at"),
    Index("ix_datasets_owner_created", "owner_id", "created_at"),
)

records = Table(
    "records", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("dataset_id", String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("tenant_id", String(36), nullable=False),
    Column("row_data", JSON, nullable=False),
    Index("ix_records_dataset_tenant", "dataset_id", "tenant_id"),
)

usage = Table(
    "usage", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("tenant_id", String(36), nullable=False),
    Column("period_key", String(32), nullable=False),
    Column("counter_name", String(80), nullable=False),
    Column("value", BigInteger, nullable=False, default=0),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("uq_usage_tenant_period_counter", "tenant_id", "period_key", "counter_name", unique=True),
)

saved_queries = Table(
    "saved_queries", metadata,
    Column("id", String(36), primary_key=True),
    Column("tenant_id", String(36), nullable=False),
    Column("dataset_id", String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(120), nullable=False),
    Column("query_config", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_saved_queries_tenant_dataset", "tenant_id", "dataset_id"),
)

audit_logs = Table(
    "audit_logs", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("tenant_id", String(36), nullable=False),
    Column("actor_id", String(36), nullable=True),
    Column("event_type", String(120), nullable=False),
    Column("event_data", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
)

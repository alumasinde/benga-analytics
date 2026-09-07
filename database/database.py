from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON,
    MetaData, String, Table, Column, create_engine, desc, func, or_, select,
)
from sqlalchemy.exc import IntegrityError

class Database:
    """MySQL-backed persistence layer for BengaAnalytics."""

    def __init__(self, database_url=None, ensure_schema=False):
        self.database_url = database_url
        from database.connection import create_database_engine
        self.engine = create_database_engine(database_url)
        self.metadata = MetaData()

        self.users = Table(
            "users", self.metadata,
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
        self.datasets = Table(
            "datasets", self.metadata,
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
        self.records = Table(
            "records", self.metadata,
            Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
            Column("dataset_id", String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            Column("tenant_id", String(36), nullable=False),
            Column("row_data", JSON, nullable=False),
            Index("ix_records_dataset_tenant", "dataset_id", "tenant_id"),
        )
        self.usage = Table(
            "usage", self.metadata,
            Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
            Column("tenant_id", String(36), nullable=False),
            Column("period_key", String(32), nullable=False),
            Column("counter_name", String(80), nullable=False),
            Column("value", BigInteger, nullable=False, default=0),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            Index("uq_usage_tenant_period_counter", "tenant_id", "period_key", "counter_name", unique=True),
        )
        self.saved_queries = Table(
            "saved_queries", self.metadata,
            Column("id", String(36), primary_key=True),
            Column("tenant_id", String(36), nullable=False),
            Column("dataset_id", String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
            Column("name", String(120), nullable=False),
            Column("query_config", JSON, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Index("ix_saved_queries_tenant_dataset", "tenant_id", "dataset_id"),
        )
        self.audit_logs = Table(
            "audit_logs", self.metadata,
            Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
            Column("tenant_id", String(36), nullable=False),
            Column("actor_id", String(36), nullable=True),
            Column("event_type", String(120), nullable=False),
            Column("event_data", JSON, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        )
        if ensure_schema:
            self.ensure_schema()

    def ensure_schema(self):
        self.metadata.create_all(self.engine)

    def ping(self):
        with self.engine.connect() as connection:
            connection.execute(select(1))

    def close(self):
        self.engine.dispose()

    @staticmethod
    def _row(row):
        return dict(row._mapping) if row else None

    @staticmethod
    def _json_path(field):
        escaped = str(field).replace("\\", "\\\\").replace('"', '\\"')
        return '$."' + escaped + '"'

    def _json_scalar(self, field):
        path = self._json_path(field)
        if self.engine.dialect.name == "sqlite":
            return func.json_extract(self.records.c.row_data, path)
        return func.JSON_UNQUOTE(func.JSON_EXTRACT(self.records.c.row_data, path))

    def create_user(self, user):
        with self.engine.begin() as connection:
            connection.execute(self.users.insert().values(**user))

    def get_user_by_id(self, user_id):
        with self.engine.connect() as connection:
            return self._row(connection.execute(
                select(self.users).where(
                    self.users.c.id == user_id,
                    self.users.c.active.is_(True),
                )
            ).first())

    def get_user_by_email(self, email):
        with self.engine.connect() as connection:
            return self._row(connection.execute(
                select(self.users).where(
                    self.users.c.email == email,
                    self.users.c.active.is_(True),
                )
            ).first())

    def count_datasets(self, tenant_id):
        with self.engine.connect() as connection:
            return connection.execute(
                select(func.count()).select_from(self.datasets).where(
                    self.datasets.c.tenant_id == tenant_id
                )
            ).scalar_one()

    def list_datasets(self, tenant_id, limit=100):
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(self.datasets)
                .where(self.datasets.c.tenant_id == tenant_id)
                .order_by(desc(self.datasets.c.created_at))
                .limit(limit)
            ).all()
            return [self._row(row) for row in rows]

    def get_dataset(self, dataset_id, tenant_id):
        with self.engine.connect() as connection:
            return self._row(connection.execute(
                select(self.datasets).where(
                    self.datasets.c.id == dataset_id,
                    self.datasets.c.tenant_id == tenant_id,
                )
            ).first())

    def create_dataset_with_records(self, dataset, records, batch_size=5000):
        with self.engine.begin() as connection:
            connection.execute(self.datasets.insert().values(**dataset))
            for offset in range(0, len(records), batch_size):
                connection.execute(
                    self.records.insert(),
                    records[offset:offset + batch_size],
                )

    def query_records(
        self, *, dataset_id, tenant_id, aggregation, metric, group_by,
        filters, search, dimensions,
    ):
        conditions = [
            self.records.c.dataset_id == dataset_id,
            self.records.c.tenant_id == tenant_id,
        ]
        for field, values in filters.items():
            if values:
                conditions.append(
                    self._json_scalar(field).in_(
                        [str(value) for value in values[:1000]]
                    )
                )
        if search and dimensions:
            pattern = f"%{search[:200].lower()}%"
            conditions.append(or_(*[
                func.lower(self._json_scalar(field)).like(pattern)
                for field in dimensions
            ]))

        if aggregation == "count":
            value_expr = func.count()
        else:
            metric_expr = self._json_scalar(metric).cast(Float)
            value_expr = (
                func.sum(metric_expr)
                if aggregation == "sum"
                else func.avg(metric_expr)
            )

        with self.engine.connect() as connection:
            if group_by:
                label_expr = self._json_scalar(group_by).label("label")
                statement = (
                    select(label_expr, value_expr.label("value"))
                    .where(*conditions)
                    .group_by(label_expr)
                    .order_by(desc(value_expr))
                    .limit(1000)
                )
                grouped = [
                    {
                        "label": str(row.label) if row.label is not None else "Unknown",
                        "value": float(row.value or 0),
                    }
                    for row in connection.execute(statement).all()
                ]
            else:
                value = connection.execute(
                    select(value_expr.label("value")).where(*conditions)
                ).scalar_one()
                grouped = [{"label": "All Records", "value": float(value or 0)}]

            raw = [
                row.row_data
                for row in connection.execute(
                    select(self.records.c.row_data)
                    .where(*conditions)
                    .order_by(self.records.c.id.asc())
                    .limit(100)
                ).all()
            ]
        return grouped, raw


db = None


def init_database():
    global db
    if db is None:
        db = Database()
    return db


__all__ = ["Database", "IntegrityError", "init_database"]

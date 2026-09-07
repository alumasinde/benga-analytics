from sqlalchemy import Float, desc, func, or_, select
from sqlalchemy.exc import IntegrityError

from database.base import metadata
from database.connection import create_database_engine
from database.models import audit_logs, datasets, records, saved_queries, usage, users


class Database:
    """Persistence facade over the versioned BengaAnalytics schema."""

    def __init__(self, database_url=None, ensure_schema=False):
        self.database_url = database_url
        self.engine = create_database_engine(database_url)
        self.metadata = metadata
        self.users = users
        self.datasets = datasets
        self.records = records
        self.usage = usage
        self.saved_queries = saved_queries
        self.audit_logs = audit_logs
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

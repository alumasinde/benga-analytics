from sqlalchemy import desc, func, select
from database.repositories.base import BaseRepository

class DatasetRepository(BaseRepository):
    def count_for_tenant(self, tenant_id):
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(self.database.datasets).where(
                self.database.datasets.c.tenant_id == tenant_id
            )).scalar_one()

    def list_for_tenant(self, tenant_id, limit=100):
        with self.engine.connect() as connection:
            rows = connection.execute(select(self.database.datasets).where(
                self.database.datasets.c.tenant_id == tenant_id
            ).order_by(desc(self.database.datasets.c.created_at)).limit(limit)).all()
            return [self.database._row(row) for row in rows]

    def get_for_tenant(self, dataset_id, tenant_id):
        with self.engine.connect() as connection:
            return self.database._row(connection.execute(select(self.database.datasets).where(
                self.database.datasets.c.id == dataset_id,
                self.database.datasets.c.tenant_id == tenant_id,
            )).first())

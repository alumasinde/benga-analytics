from sqlalchemy import select
from database.repositories.base import BaseRepository

class UsageRepository(BaseRepository):
    def get(self, tenant_id, period_key, counter_name):
        with self.engine.connect() as connection:
            return self.database._row(connection.execute(select(self.database.usage).where(
                self.database.usage.c.tenant_id == tenant_id,
                self.database.usage.c.period_key == period_key,
                self.database.usage.c.counter_name == counter_name,
            )).first())

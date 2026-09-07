from database.repositories.base import BaseRepository

class AuditRepository(BaseRepository):
    def create(self, event):
        with self.engine.begin() as connection:
            connection.execute(self.database.audit_logs.insert().values(**event))

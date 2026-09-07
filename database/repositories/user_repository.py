from sqlalchemy import select
from database.repositories.base import BaseRepository

class UserRepository(BaseRepository):
    def create(self, user):
        with self.engine.begin() as connection:
            connection.execute(self.database.users.insert().values(**user))

    def get_by_id(self, user_id):
        with self.engine.connect() as connection:
            return self.database._row(connection.execute(select(self.database.users).where(
                self.database.users.c.id == user_id,
                self.database.users.c.active.is_(True),
            )).first())

    def get_by_email(self, email):
        with self.engine.connect() as connection:
            return self.database._row(connection.execute(select(self.database.users).where(
                self.database.users.c.email == email,
                self.database.users.c.active.is_(True),
            )).first())

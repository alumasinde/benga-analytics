from database.repositories.base import BaseRepository

class RecordRepository(BaseRepository):
    def create_dataset_with_records(self, dataset, rows, batch_size=5000):
        with self.engine.begin() as connection:
            connection.execute(self.database.datasets.insert().values(**dataset))
            for offset in range(0, len(rows), batch_size):
                connection.execute(self.database.records.insert(), rows[offset:offset + batch_size])

    def query(self, **kwargs):
        return self.database.query_records(**kwargs)

class BaseRepository:
    def __init__(self, database):
        self.database = database
        self.engine = database.engine

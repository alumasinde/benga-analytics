import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()


class Database:
    """MongoDB access layer with explicit client injection for testability."""

    def __init__(self, client=None, db_name=None, ensure_indexes=True):
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
        resolved_db_name = db_name or os.getenv("MONGODB_DB", "benga_analytics")

        self.client = client or MongoClient(
            uri,
            maxPoolSize=int(os.getenv("MONGO_MAX_POOL_SIZE", "100")),
            minPoolSize=int(os.getenv("MONGO_MIN_POOL_SIZE", "5")),
            retryWrites=True,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
        )
        self.db = self.client[resolved_db_name]
        self.users = self.db.users
        self.datasets = self.db.datasets
        self.records = self.db.records
        self.usage = self.db.usage
        self.saved_queries = self.db.saved_queries
        self.audit_logs = self.db.audit_logs

        if ensure_indexes:
            self.ensure_indexes()

    def ensure_indexes(self):
        self.users.create_index([("email", ASCENDING)], unique=True)
        self.users.create_index([("tenant_id", ASCENDING)])
        self.datasets.create_index([("tenant_id", ASCENDING), ("created_at", DESCENDING)])
        self.datasets.create_index([("owner_id", ASCENDING), ("created_at", DESCENDING)])
        self.records.create_index([("dataset_id", ASCENDING)])
        self.usage.create_index([("tenant_id", ASCENDING), ("period_key", ASCENDING)], unique=True)
        self.saved_queries.create_index([("tenant_id", ASCENDING), ("dataset_id", ASCENDING)])
        self.audit_logs.create_index([("tenant_id", ASCENDING), ("created_at", DESCENDING)])

    def ping(self):
        self.client.admin.command("ping")

    def close(self):
        self.client.close()


db = None\n\ndef init_database():\n    global db\n    if db is None:\n        db = Database()\n    return db

import os

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

load_dotenv()


class Database:
    """MongoDB access layer with explicit client injection for testability."""

    def __init__(self, client=None, db_name=None, ensure_indexes=False):
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

    @staticmethod
    def _keys_match(index, keys):
        return list(index.get("key", {}).items()) == list(keys)

    def _ensure_index(self, collection, keys, *, name, unique=False):
        """Create or reconcile an index definition without startup conflicts."""
        existing = next(
            (index for index in collection.list_indexes() if index.get("name") == name),
            None,
        )

        if existing:
            matches_keys = self._keys_match(existing, keys)
            matches_unique = bool(existing.get("unique", False)) == unique

            if matches_keys and matches_unique:
                return name

            if unique:
                fields = [field for field, _ in keys]
                duplicate = next(
                    collection.aggregate(
                        [
                            {
                                "$match": {
                                    field: {"$exists": True, "$ne": None}
                                    for field in fields
                                }
                            },
                            {
                                "$group": {
                                    "_id": {
                                        field: "$" + field
                                        for field in fields
                                    },
                                    "count": {"$sum": 1},
                                }
                            },
                            {"$match": {"count": {"$gt": 1}}},
                            {"$limit": 1},
                        ]
                    ),
                    None,
                )
                if duplicate:
                    raise RuntimeError(
                        f"Cannot upgrade index '{name}' to unique because duplicate "
                        f"values already exist for {fields}. Resolve the duplicate "
                        "documents before restarting BengaAnalytics."
                    )

            collection.drop_index(name)

        return collection.create_index(keys, name=name, unique=unique)

    def ensure_indexes(self):
        self._ensure_index(
            self.users,
            [("email", ASCENDING)],
            name="users_email_unique",
            unique=True,
        )
        self._ensure_index(
            self.users,
            [("tenant_id", ASCENDING)],
            name="users_tenant_id_unique",
            unique=True,
        )
        self._ensure_index(
            self.datasets,
            [("tenant_id", ASCENDING), ("created_at", DESCENDING)],
            name="datasets_tenant_created_at",
        )
        self._ensure_index(
            self.datasets,
            [("owner_id", ASCENDING), ("created_at", DESCENDING)],
            name="datasets_owner_created_at",
        )
        self._ensure_index(
            self.records,
            [("dataset_id", ASCENDING)],
            name="records_dataset_id",
        )
        self._ensure_index(
            self.usage,
            [("tenant_id", ASCENDING), ("period_key", ASCENDING)],
            name="usage_tenant_period_unique",
            unique=True,
        )
        self._ensure_index(
            self.saved_queries,
            [("tenant_id", ASCENDING), ("dataset_id", ASCENDING)],
            name="saved_queries_tenant_dataset",
        )
        self._ensure_index(
            self.audit_logs,
            [("tenant_id", ASCENDING), ("created_at", DESCENDING)],
            name="audit_logs_tenant_created_at",
        )

    def ping(self):
        self.client.admin.command("ping")

    def close(self):
        self.client.close()


db = None


def init_database():
    global db
    if db is None:
        db = Database()
    return db

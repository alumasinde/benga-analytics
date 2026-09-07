import uuid
from datetime import datetime, timezone
from analyzer import dataframe_records, infer_and_clean, read_dataframe
from database.repositories import AuditRepository, DatasetRepository, RecordRepository

class DatasetService:
    def __init__(self, database):
        self.datasets = DatasetRepository(database); self.records = RecordRepository(database); self.audit = AuditRepository(database)
    def list(self, tenant_id): return self.datasets.list_for_tenant(tenant_id)
    def count(self, tenant_id): return self.datasets.count_for_tenant(tenant_id)
    def get(self, dataset_id, tenant_id): return self.datasets.get_for_tenant(dataset_id, tenant_id)
    def ingest(self, user, file):
        df = read_dataframe(file); df, metadata = infer_and_clean(df)
        dataset_id=str(uuid.uuid4()); created=datetime.now(timezone.utc)
        dataset={"id":dataset_id,"tenant_id":user["tenant_id"],"owner_id":user["id"],"filename":file.filename,"created_at":created,"updated_at":created,"status":"ready","schema_metadata":metadata,"row_count":metadata["row_count"]}
        rows=[{"dataset_id":dataset_id,"tenant_id":user["tenant_id"],"row_data":row} for row in dataframe_records(df)]
        self.records.create_dataset_with_records(dataset, rows)
        self.audit.create({"tenant_id":user["tenant_id"],"actor_id":user["id"],"event_type":"dataset.uploaded","event_data":{"dataset_id":dataset_id,"filename":file.filename,"row_count":metadata["row_count"]},"created_at":created})
        return dataset, metadata

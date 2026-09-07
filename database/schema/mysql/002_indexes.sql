CREATE INDEX ix_datasets_tenant_created ON datasets (tenant_id, created_at);
CREATE INDEX ix_datasets_owner_created ON datasets (owner_id, created_at);
CREATE INDEX ix_records_dataset_tenant ON records (dataset_id, tenant_id);
CREATE INDEX ix_saved_queries_tenant_dataset ON saved_queries (tenant_id, dataset_id);
CREATE INDEX ix_audit_logs_tenant_created ON audit_logs (tenant_id, created_at);

-- BengaAnalytics MySQL baseline schema
-- MySQL 8.0+ / InnoDB / utf8mb4
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) NOT NULL,
  tenant_id CHAR(36) NOT NULL,
  first_name VARCHAR(80) NOT NULL,
  last_name VARCHAR(80) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  tier VARCHAR(50) NOT NULL,
  subscription JSON NOT NULL,
  terms JSON NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_tenant_id (tenant_id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS datasets (
  id CHAR(36) NOT NULL,
  tenant_id CHAR(36) NOT NULL,
  owner_id CHAR(36) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  status VARCHAR(30) NOT NULL,
  schema_metadata JSON NOT NULL,
  row_count BIGINT NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_datasets_owner_id_users FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  dataset_id CHAR(36) NOT NULL,
  tenant_id CHAR(36) NOT NULL,
  row_data JSON NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_records_dataset_id_datasets FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usage (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id CHAR(36) NOT NULL,
  period_key VARCHAR(32) NOT NULL,
  counter_name VARCHAR(80) NOT NULL,
  value BIGINT NOT NULL DEFAULT 0,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_usage_tenant_period_counter (tenant_id, period_key, counter_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS saved_queries (
  id CHAR(36) NOT NULL,
  tenant_id CHAR(36) NOT NULL,
  dataset_id CHAR(36) NOT NULL,
  name VARCHAR(120) NOT NULL,
  query_config JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_saved_queries_dataset_id_datasets FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id CHAR(36) NOT NULL,
  actor_id CHAR(36) NULL,
  event_type VARCHAR(120) NOT NULL,
  event_data JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

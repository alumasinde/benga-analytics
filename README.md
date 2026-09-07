# BengaAnalytics

BengaAnalytics is a production-oriented, multi-tenant Business Intelligence platform built with Flask, MySQL, Pandas and vanilla JavaScript.

## Database architecture

The platform now uses MySQL instead of MongoDB.

- users stores authentication, tenants and subscription lifecycle data.
- datasets stores uploaded file metadata and the dynamically discovered schema.
- records stores each uploaded row as a JSON document linked to its dataset and tenant.
- usage, saved_queries and audit_logs support commercial features.

This hybrid model keeps stable SaaS entities relational while allowing Business, Education, Healthcare and other industries to upload completely different column structures without schema rewrites.

Every query is tenant-scoped and dataset-scoped. The records(dataset_id, tenant_id) index narrows analytical scans before dynamic JSON fields are evaluated.

## Local MySQL setup

Create the database:

~~~sql
CREATE DATABASE benga_analytics
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
~~~

Copy .env.example to .env and set your MySQL credentials:

~~~env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@127.0.0.1:3306/benga_analytics?charset=utf8mb4
~~~

## Run

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -v
python app.py
~~~

On first startup BengaAnalytics creates the relational schema and indexes.

## CI

GitHub Actions runs the test suite on Python 3.11 and 3.12. The test suite uses an isolated in-memory SQL database so CI remains fast and does not depend on an external server.

Production uses MySQL through SQLAlchemy with PyMySQL, connection pooling, pre-ping and connection recycling.

## Database schema and migrations

The repository contains the production MySQL schema in:

- `database/schema/mysql/001_initial_schema.sql`
- `database/schema/mysql/002_indexes.sql`
- `database/schema/mysql/003_seed_plans.sql`

For a fresh manual MySQL installation, run the SQL files in numeric order after creating the database.

For version-controlled application migrations:

~~~powershell
alembic upgrade head
~~~

The migration environment reads `DATABASE_URL` from your environment. Do not use automatic schema creation as a replacement for migrations in a managed production deployment.

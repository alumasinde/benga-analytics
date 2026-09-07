# Database schema

The SQL files in `mysql/` are the human-readable production baseline for MySQL 8.0+.

- `001_initial_schema.sql`: tables and foreign keys.
- `002_indexes.sql`: performance indexes.
- `003_seed_plans.sql`: reserved for versioned plan seed data.

For a fresh manual database installation, run the files in numeric order. Application deployments should use Alembic migrations once migrations are enabled for the environment.

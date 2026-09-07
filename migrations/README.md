# BengaAnalytics migrations

Alembic is used for versioned database changes. The SQL baseline remains available under `database/schema/mysql` for DBAs and fresh manual installations.

Never edit an applied migration. Add a new revision for every production schema change.

from app import app, db

# Production WSGI startup path.
# The schema is idempotently created here until a dedicated migration
# workflow is introduced in the next database architecture phase.
db.ping()
db.ensure_schema()

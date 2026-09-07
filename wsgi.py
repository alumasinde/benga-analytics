from app import app, db

# Production WSGI startup path: verify connectivity and create required indexes once.
db.ping()
db.ensure_indexes()

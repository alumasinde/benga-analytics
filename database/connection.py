from sqlalchemy import create_engine
from database.config import database_url, engine_options
def create_database_engine(url=None):
    resolved=url or database_url()
    return create_engine(resolved, **engine_options(resolved))

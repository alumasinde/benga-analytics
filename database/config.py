import os
from dotenv import load_dotenv
load_dotenv()
def database_url():
    return os.getenv("DATABASE_URL", "mysql+pymysql://root@127.0.0.1:3306/benga_analytics?charset=utf8mb4")
def engine_options(url):
    options={"pool_pre_ping":True,"pool_recycle":int(os.getenv("DB_POOL_RECYCLE","1800"))}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        options.update({"connect_args":{"check_same_thread":False},"poolclass":StaticPool})
    else:
        options.update({"pool_size":int(os.getenv("DB_POOL_SIZE","10")),"max_overflow":int(os.getenv("DB_MAX_OVERFLOW","20"))})
    return options

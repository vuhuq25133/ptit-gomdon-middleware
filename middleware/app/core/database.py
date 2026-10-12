import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.core.config import settings

@contextmanager
def get_db():
    conn = psycopg2.connect(
        host    =settings.POSTGRES_HOST,
        port    =settings.POSTGRES_PORT,
        dbname  =settings.POSTGRES_DB,
        user    =settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD
    )
    conn.autocommit = False
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

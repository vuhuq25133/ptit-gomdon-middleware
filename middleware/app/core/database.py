import threading
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.core.config import settings

# Hồ chứa kết nối dùng chung (Thread-safe Connection Pool)
_db_pool: pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def get_db_pool() -> pool.ThreadedConnectionPool:
    """Khởi tạo và trả về ThreadedConnectionPool (Singleton) giữ sẵn 2-20 kết nối TCP tới PostgreSQL"""
    global _db_pool
    if _db_pool is None:
        with _pool_lock:
            if _db_pool is None:
                _db_pool = pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=20,
                    host=settings.POSTGRES_HOST,
                    port=settings.POSTGRES_PORT,
                    dbname=settings.POSTGRES_DB,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                )
    return _db_pool


@contextmanager
def get_db():
    """
    Mượn 1 kết nối đang mở sẵn từ Connection Pool (tốn ~0ms thay vì mở TCP mới),
    thực thi truy vấn và trả kết nối về lại Pool khi hoàn tất.
    """
    db_pool = get_db_pool()
    conn = db_pool.getconn()
    # Nếu kết nối trong pool bị đứt bất thường thì hủy và lấy kết nối mới
    if conn.closed != 0:
        db_pool.putconn(conn, close=True)
        conn = db_pool.getconn()

    conn.autocommit = False
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
        conn.commit()
    except Exception:
        if conn.closed == 0:
            conn.rollback()
        raise
    finally:
        if cur is not None and not cur.closed:
            cur.close()
        # Trả kết nối về lại hồ chứa (Pool) để tái sử dụng, tuyệt đối không đóng TCP!
        db_pool.putconn(conn, close=(conn.closed != 0))

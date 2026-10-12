import redis
from app.core.config import settings

def get_redis_client():
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True
    )

def check_and_set_dedup(key: str, expire_seconds: int = 30) -> bool:
    """
    Sử dụng lệnh Redis SETNX (SET key value EX expire NX).
    - Trả về True nếu key chưa tồn tại -> Đặt thành công (Cho phép xử lý đơn mới).
    - Trả về False nếu key đã tồn tại -> Phát hiện click đúp / spam đơn trong vòng 30s.
    """
    client = get_redis_client()
    try:
        # SET key 1 EX expire_seconds NX
        is_new = client.set(f"dedup:{key}", "1", ex=expire_seconds, nx=True)
        return bool(is_new)
    except Exception as e:
        print(f"[!] Canh bao: Khong the ket noi Redis ({e}), bo qua dedup cache.")
        return True

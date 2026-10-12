import json
from app.core.database import get_db

def save_to_bronze(source_channel: str, source_order_id: str, raw_payload: dict) -> int:
    """
    Lưu nguyên vẹn JSON thô vào Tầng Bronze (bảng raw_orders) trong PostgreSQL.
    Đảm bảo 100% không bao giờ mất dữ liệu gốc của khách hàng.
    """
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO raw_orders (source_channel, source_order_id, raw_payload, process_status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING id;
            """,
            (source_channel, source_order_id, json.dumps(raw_payload, ensure_ascii=False))
        )
        row = cur.fetchone()
        return row["id"]

def update_bronze_status(raw_order_id: int, status: str, error_message: str = None):
    """Cập nhật trạng thái xử lý của bản ghi Bronze sau khi Worker tiếp nhận"""
    with get_db() as cur:
        cur.execute(
            """
            UPDATE raw_orders 
            SET process_status = %s, error_message = %s 
            WHERE id = %s;
            """,
            (status, error_message, raw_order_id)
        )

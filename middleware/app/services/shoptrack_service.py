import json
from hashlib import sha256

import httpx

from app.core.config import settings
from app.core.database import get_db


def push_order_to_shoptrack(order_code: str, source_metadata: dict) -> None:
    """Gửi đơn Silver sang ShopTrack và ghi lại kết quả từng lần gửi."""
    error = None
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, source_channel, source_order_id, shipping_name, shipping_phone,
                   shipping_address, shipping_city, note, total_amount, status, shoptrack_order_id
            FROM orders WHERE order_code = %s FOR UPDATE;
            """,
            (order_code,),
        )
        order = cur.fetchone()
        if order is None:
            raise ValueError(f"Không tìm thấy đơn Silver {order_code}")
        if order["shoptrack_order_id"]:
            return
        if order["status"] != "processing":
            raise ValueError(f"Đơn Silver {order_code} chưa sẵn sàng để đồng bộ")

        cur.execute("SELECT sku, quantity, price FROM order_items WHERE order_id = %s ORDER BY id;", (order["id"],))
        payload = {
            "source_channel": order["source_channel"],
            "source_order_id": order["source_order_id"],
            "source_metadata": source_metadata,
            "customer_name": order["shipping_name"],
            "customer_phone": order["shipping_phone"],
            "shipping_address": order["shipping_address"],
            "shipping_city": order["shipping_city"],
            "note": order["note"],
            "items": [{**item, "price": float(item["price"])} for item in cur.fetchall()],
            "total_amount": float(order["total_amount"]),
        }
        source_key = f"{order['source_channel']}:{order['source_order_id']}"
        idempotency_key = sha256(source_key.encode()).hexdigest()

        http_status = None
        response_payload = None
        try:
            response = httpx.post(
                f"{settings.SHOPTRACK_API_BASE_URL.rstrip('/')}/orders",
                json=payload,
                headers={"X-Idempotency-Key": idempotency_key},
                timeout=5.0,
            )
            http_status = response.status_code
            response_payload = response.json()
            response.raise_for_status()
            if not isinstance(response_payload, dict):
                raise ValueError("Phản hồi ShopTrack không phải đối tượng JSON")
            partner_id = response_payload.get("order_id")
            tracking_code = response_payload.get("tracking_code")
            if not isinstance(partner_id, str) or not 1 <= len(partner_id.strip()) <= 50:
                raise ValueError("Phản hồi ShopTrack thiếu mã đơn hợp lệ")
            if tracking_code is not None and (not isinstance(tracking_code, str) or len(tracking_code) > 50):
                raise ValueError("Phản hồi ShopTrack có mã vận đơn không hợp lệ")
        except (httpx.HTTPError, ValueError) as exc:
            error = exc
            if response_payload is None:
                response_payload = {"error": str(exc)}

        cur.execute(
            """
            INSERT INTO sync_audit_logs (order_id, action, request_payload, response_payload, http_status, status)
            VALUES (%s, 'push_to_shoptrack', %s, %s, %s, %s);
            """,
            (
                order["id"],
                json.dumps(payload, ensure_ascii=False),
                json.dumps(response_payload, ensure_ascii=False),
                http_status,
                "failed" if error else "success",
            ),
        )
        if error is None:
            cur.execute(
                """
                UPDATE orders SET status = 'pushed_to_shoptrack', shoptrack_order_id = %s,
                                  tracking_code = %s, updated_at = NOW()
                WHERE id = %s;
                """,
                (partner_id.strip(), tracking_code, order["id"]),
            )

    # Commit nhật ký lỗi trước khi yêu cầu Worker thử lại hoặc chuyển đơn vào DLQ.
    if error is not None:
        raise RuntimeError(f"Không thể đồng bộ đơn {order_code} sang ShopTrack") from error

"""
ShopTrack Outbound Synchronization Service (Task 5.1 / Market-5)
================================================================
Đồng bộ đơn hàng đủ điều kiện ('processing') từ Tầng Silver sang hệ thống
quản lý kho & vận đơn đối tác ShopTrack:
1. Đính kèm khóa chống đẩy trùng `X-Idempotency-Key: {source_channel}_{source_order_id}`.
2. Cập nhật `shoptrack_order_id` (`ST_...`), `tracking_code` (`VNPOST_...`) và
   trạng thái `pushed_to_shoptrack` vào bảng `orders`.
3. Lưu vết toàn bộ Request / Response vào bảng `sync_audit_logs` phục vụ đối soát.
"""
import json
from typing import Dict, Any, Optional
import urllib.request
import urllib.error

from app.core.config import settings
from app.core.database import get_db


def push_order_to_shoptrack(order_code: str) -> Dict[str, Any]:
    """
    Đẩy đơn hàng đã chuẩn hóa (theo `order_code`) sang ShopTrack API
    và ghi nhận lịch sử vào bảng `sync_audit_logs`.
    """
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, order_code, source_channel, source_order_id,
                   shipping_name, shipping_phone, shipping_address, shipping_city,
                   total_amount, status, note, shoptrack_order_id, tracking_code
            FROM orders
            WHERE order_code = %s
            LIMIT 1;
            """,
            (order_code,)
        )
        order = cur.fetchone()
        if not order:
            return {"success": False, "error": f"Không tìm thấy đơn hàng {order_code}"}

        # Nếu đơn đã đẩy thành công trước đó -> Trả về kết quả cũ ngay (Idempotent)
        if order["status"] == "pushed_to_shoptrack" and order.get("shoptrack_order_id"):
            return {
                "success": True,
                "already_pushed": True,
                "shoptrack_order_id": order["shoptrack_order_id"],
                "tracking_code": order["tracking_code"],
            }

        cur.execute(
            """
            SELECT sku, product_name, quantity, price
            FROM order_items
            WHERE order_id = %s
            ORDER BY id ASC;
            """,
            (order["id"],)
        )
        items_rows = cur.fetchall()

    payload = {
        "source_channel": order["source_channel"],
        "source_order_id": order["source_order_id"] or order["order_code"],
        "customer_name": order["shipping_name"],
        "customer_phone": order["shipping_phone"],
        "shipping_address": order["shipping_address"],
        "shipping_city": order["shipping_city"],
        "note": order.get("note"),
        "items": [
            {
                "sku": r["sku"],
                "quantity": int(r["quantity"]),
                "price": float(r["price"])
            }
            for r in items_rows
        ],
        "total_amount": float(order["total_amount"])
    }

    idempotency_key = f"{order['source_channel']}_{order['source_order_id'] or order['order_code']}"
    req_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        settings.SHOPTRACK_API_URL,
        data=req_bytes,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Idempotency-Key": idempotency_key,
        },
        method="POST",
    )

    http_status = 0
    resp_data: Dict[str, Any] = {}
    sync_status = "failed"

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            http_status = resp.getcode()
            raw_body = resp.read().decode("utf-8")
            resp_data = json.loads(raw_body) if raw_body else {}
            if 200 <= http_status < 300:
                sync_status = "success"
    except urllib.error.HTTPError as http_err:
        http_status = http_err.code
        try:
            err_body = http_err.read().decode("utf-8")
            resp_data = json.loads(err_body) if err_body else {"error": str(http_err)}
        except Exception:
            resp_data = {"error": str(http_err)}
    except Exception as exc:
        http_status = 503
        resp_data = {"error": f"ShopTrack server chưa kết nối ({exc})"}

    # Ghi nhật ký đồng bộ vào sync_audit_logs & cập nhật trạng thái đơn hàng
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO sync_audit_logs (
                order_id, action, request_payload, response_payload, http_status, status
            ) VALUES (
                %s, 'push_to_shoptrack', %s::jsonb, %s::jsonb, %s, %s
            );
            """,
            (
                order["id"],
                json.dumps(payload, ensure_ascii=False),
                json.dumps(resp_data, ensure_ascii=False),
                http_status,
                sync_status,
            )
        )

        if sync_status == "success":
            st_order_id = resp_data.get("order_id") or f"ST_{order['id']:05d}"
            tracking_code = resp_data.get("tracking_code") or f"VNPOST_{st_order_id}"
            cur.execute(
                """
                UPDATE orders
                SET status = 'pushed_to_shoptrack',
                    shoptrack_order_id = %s,
                    tracking_code = %s,
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (st_order_id, tracking_code, order["id"])
            )
            print(
                f"   🚚 [SHOPTRACK SYNC OK] Đơn {order_code} -> ShopTrack ID: {st_order_id} | Vận đơn: {tracking_code}"
            )
            return {
                "success": True,
                "shoptrack_order_id": st_order_id,
                "tracking_code": tracking_code,
                "http_status": http_status,
            }
        else:
            print(
                f"   ⚠️  [SHOPTRACK SYNC PENDING] Đã ghi nhận vào sync_audit_logs (HTTP {http_status}): {resp_data.get('error', resp_data)}"
            )
            return {
                "success": False,
                "http_status": http_status,
                "error": resp_data.get("error", "Failed to push to ShopTrack"),
            }


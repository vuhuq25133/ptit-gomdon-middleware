from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
from app.core.database import get_db

def get_or_create_customer(phone: str, full_name: str, address: str, city: str) -> int:
    """
    Quy tắc nghiệp vụ: 'Một khách hàng - Một hồ sơ duy nhất' (Dedup theo SĐT).
    - Nếu SĐT đã có trong DB: Cập nhật địa chỉ mới nhất.
    - Nếu SĐT chưa có: Tạo bản ghi khách hàng mới.
    """
    with get_db() as cur:
        cur.execute("SELECT id, full_name FROM customers WHERE phone = %s;", (phone,))
        existing = cur.fetchone()

        if existing:
            # Khách quen: Cập nhật địa chỉ và họ tên nếu mới hơn
            cur.execute(
                """
                UPDATE customers 
                SET full_name = COALESCE(%s, full_name),
                    shipping_address = COALESCE(%s, shipping_address),
                    shipping_city = COALESCE(%s, shipping_city),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id;
                """,
                (full_name, address, city, existing["id"])
            )
            return existing["id"]
        else:
            # Khách mới: Thêm vào danh bạ
            cur.execute(
                """
                INSERT INTO customers (phone, full_name, shipping_address, shipping_city)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (phone, full_name, address, city)
            )
            new_cust = cur.fetchone()
            return new_cust["id"]

def link_customer_identity(customer_id: int, channel: str, identity_value: str) -> None:
    """
    Ánh xạ tài khoản mạng xã hội (PSID Facebook, User ID Zalo) với customer_id.
    Bảo đảm quy tắc: 'Một khách hàng - Nhiều định danh đa kênh'.
    """
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO customer_identities (customer_id, channel, identity_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (channel, identity_value) 
            DO UPDATE SET customer_id = EXCLUDED.customer_id;
            """,
            (customer_id, channel, identity_value)
        )

def get_customer_id_by_identity(channel: str, identity_value: str) -> Optional[int]:
    """Tra cứu customer_id từ định danh kênh (ví dụ: tìm customer_id từ Facebook PSID)"""
    with get_db() as cur:
        cur.execute(
            "SELECT customer_id FROM customer_identities WHERE channel = %s AND identity_value = %s;",
            (channel, identity_value)
        )
        row = cur.fetchone()
        return row["customer_id"] if row else None

def get_or_create_conversation(
    channel: str, 
    channel_conversation_id: str, 
    customer_id: Optional[int] = None,
    sender_name: Optional[str] = None,
    sender_avatar: Optional[str] = None
) -> int:
    """
    Quản lý cuộc hội thoại trong bảng conversations (Cột 1 giao diện ChatbotX / Pancake).
    Lưu trữ channel_conversation_id, customer_id, sender_name (Facebook Nickname), sender_avatar.
    """
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, customer_id, sender_name, sender_avatar FROM conversations 
            WHERE channel = %s AND channel_conversation_id = %s;
            """,
            (channel, channel_conversation_id)
        )
        existing = cur.fetchone()
        if existing:
            updates = []
            params = []
            if customer_id and not existing["customer_id"]:
                updates.append("customer_id = %s")
                params.append(customer_id)
            if sender_name and not existing.get("sender_name"):
                updates.append("sender_name = %s")
                params.append(sender_name)
            if sender_avatar and not existing.get("sender_avatar"):
                updates.append("sender_avatar = %s")
                params.append(sender_avatar)
            
            if updates:
                params.append(existing["id"])
                cur.execute(f"UPDATE conversations SET {', '.join(updates)} WHERE id = %s;", tuple(params))
            return existing["id"]

        cur.execute(
            """
            INSERT INTO conversations (channel, channel_conversation_id, customer_id, sender_name, sender_avatar)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (channel, channel_conversation_id, customer_id, sender_name, sender_avatar)
        )
        row = cur.fetchone()
        return row["id"]

def save_chat_message(conversation_id: int, sender_type: str, content: str, has_extracted_order: bool = False) -> int:
    """
    Lưu nội dung tin nhắn vào bảng messages (Cột 2 giao diện Chat).
    sender_type: 'customer' hoặc 'shop'
    """
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO messages (conversation_id, sender_type, content, has_extracted_order)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (conversation_id, sender_type, content, has_extracted_order)
        )
        row = cur.fetchone()
        return row["id"]

def create_silver_order(
    raw_order_id: int,
    source_channel: str,
    source_order_id: str,
    customer_id: int,
    shipping_name: str,
    shipping_phone: str,
    shipping_address: str,
    shipping_city: str,
    items: list,
    total_amount: float,
    status: str = "processing",
    note: str = None
) -> str:
    """
    Chuẩn hóa và lưu trữ vào Tầng Silver (bảng orders và order_items).
    Bảo đảm tính Idempotent theo cặp (source_channel, source_order_id).
    status:
      - 'processing': Tự động chốt đối với đơn Landing Page / Sàn TMĐT.
      - 'draft': Đơn nháp chờ nhân viên duyệt đối với Social Chat (Facebook / Zalo).
    """
    # Sinh mã đơn chuẩn nội bộ: ORD_YYYYMMDD_XXXXXX
    today_str = datetime.now().strftime("%Y%m%d")
    order_code = f"ORD_{today_str}_{uuid.uuid4().hex[:6].upper()}"

    with get_db() as cur:
        # 1. Tạo bản ghi đơn hàng chuẩn hóa (Silver) kèm ON CONFLICT chống nhân đôi đơn
        cur.execute(
            """
            INSERT INTO orders (
                order_code, source_channel, source_order_id, customer_id,
                shipping_name, shipping_phone, shipping_address, shipping_city,
                total_amount, status, raw_order_id, note
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (source_channel, source_order_id) DO NOTHING
            RETURNING id, order_code;
            """,
            (
                order_code, source_channel, source_order_id, customer_id,
                shipping_name, shipping_phone, shipping_address, shipping_city,
                total_amount, status, raw_order_id, note
            )
        )
        order_row = cur.fetchone()
        if not order_row:
            # Đơn hàng đã tồn tại do retry -> Trả về order_code cũ mà không tạo trùng order_items
            cur.execute(
                "SELECT order_code FROM orders WHERE source_channel = %s AND source_order_id = %s;",
                (source_channel, source_order_id)
            )
            existing_order = cur.fetchone()
            return existing_order["order_code"] if existing_order else order_code

        order_id = order_row["id"]

        # 2. Tạo các dòng chi tiết sản phẩm (order_items)
        for item in items:
            cur.execute(
                """
                INSERT INTO order_items (order_id, sku, product_name, quantity, price)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    order_id,
                    item.get("sku"),
                    item.get("product_name", item.get("name", f"Sản phẩm {item.get('sku')}")),
                    item.get("quantity", 1),
                    item.get("price", item.get("unit_price", 0.0))
                )
            )

    return order_code


def get_existing_draft_order(customer_id: int, channel: str = "facebook") -> Optional[Dict[str, Any]]:
    """
    Tra cứu đơn nháp ('draft') gần nhất của khách hàng trên kênh tương ứng chưa được chốt.
    Giúp gộp các tin nhắn bổ sung thông tin vào cùng một đơn nháp duy nhất.
    """
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, order_code, shipping_name, shipping_phone, shipping_address, shipping_city, total_amount, note
            FROM orders
            WHERE customer_id = %s AND status = 'draft' AND source_channel = %s
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            (customer_id, channel)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_silver_draft_order(
    order_id: int,
    raw_order_id: int,
    shipping_name: Optional[str] = None,
    shipping_phone: Optional[str] = None,
    shipping_address: Optional[str] = None,
    shipping_city: Optional[str] = None,
    items: Optional[list] = None,
    total_amount: Optional[float] = None,
    note: Optional[str] = None
) -> str:
    """
    Cập nhật làm giàu (enrich) thông tin vào đơn nháp hiện có khi khách chat bổ sung thông tin.
    Quy tắc an toàn: Không đè thông tin tốt có sẵn bằng giá trị rỗng hoặc 'Chưa rõ'.
    """
    with get_db() as cur:
        cur.execute(
            """
            SELECT order_code, shipping_name, shipping_phone, shipping_address, shipping_city, total_amount
            FROM orders WHERE id = %s;
            """,
            (order_id,)
        )
        cur_order = cur.fetchone()
        if not cur_order:
            return ""

        # Lọc giá trị mới hợp lệ
        new_name = cur_order["shipping_name"]
        if shipping_name and "Khách Facebook" not in shipping_name:
            new_name = shipping_name

        new_phone = shipping_phone or cur_order["shipping_phone"]

        new_address = cur_order["shipping_address"]
        if shipping_address and "Chưa rõ" not in shipping_address:
            new_address = shipping_address

        new_city = cur_order["shipping_city"]
        if shipping_city and "Chưa rõ" not in shipping_city:
            new_city = shipping_city

        new_total = cur_order["total_amount"]
        if total_amount and total_amount > 0:
            new_total = total_amount

        # Cập nhật bảng orders
        cur.execute(
            """
            UPDATE orders
            SET shipping_name = %s,
                shipping_phone = %s,
                shipping_address = %s,
                shipping_city = %s,
                total_amount = %s,
                raw_order_id = %s,
                note = COALESCE(%s, note),
                updated_at = NOW()
            WHERE id = %s;
            """,
            (new_name, new_phone, new_address, new_city, new_total, raw_order_id, note, order_id)
        )

        # Cập nhật order_items nếu tin mới có sản phẩm cụ thể (không phải gợi ý mặc định)
        if items and len(items) > 0:
            is_default = any("Gợi ý mặc định" in it.get("name", "") for it in items)
            if not is_default:
                cur.execute("DELETE FROM order_items WHERE order_id = %s;", (order_id,))
                for item in items:
                    cur.execute(
                        """
                        INSERT INTO order_items (order_id, sku, product_name, quantity, price)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (
                            order_id,
                            item.get("sku"),
                            item.get("product_name", item.get("name", f"Sản phẩm {item.get('sku')}")),
                            item.get("quantity", 1),
                            item.get("price", item.get("unit_price", 0.0))
                        )
                    )

        return cur_order["order_code"]

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
    note: str = None
) -> str:
    """
    Chuẩn hóa và lưu trữ vào Tầng Silver (bảng orders và order_items).
    Trạng thái ban đầu: 'processing' (Sẵn sàng trong kho, chưa cần đẩy đối tác).
    """
    # Sinh mã đơn chuẩn nội bộ: ORD_YYYYMMDD_XXXXXX
    today_str = datetime.now().strftime("%Y%m%d")
    order_code = f"ORD_{today_str}_{uuid.uuid4().hex[:6].upper()}"

    with get_db() as cur:
        # 1. Tạo bản ghi đơn hàng chuẩn hóa (Silver)
        cur.execute(
            """
            INSERT INTO orders (
                order_code, source_channel, source_order_id, customer_id,
                shipping_name, shipping_phone, shipping_address, shipping_city,
                total_amount, status, raw_order_id, note
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, 'processing', %s, %s
            ) RETURNING id;
            """,
            (
                order_code, source_channel, source_order_id, customer_id,
                shipping_name, shipping_phone, shipping_address, shipping_city,
                total_amount, raw_order_id, note
            )
        )
        order_row = cur.fetchone()
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
                    item.get("product_name", f"Sản phẩm {item.get('sku')}"),
                    item.get("quantity", 1),
                    item.get("price", 0.0)
                )
            )

    return order_code

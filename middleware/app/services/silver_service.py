from typing import Optional, List, Dict, Any
import hashlib
import re
import uuid
from datetime import datetime
from app.core.database import get_db
from app.core.catalog import PRODUCT_CATALOG, get_product_by_sku
from app.services.chat_extractor import extract_phone


def normalize_or_isolate_phone(
    phone: str,
    external_ref: Optional[str] = None,
    full_name: Optional[str] = None
) -> str:
    """
    Chuẩn hóa SĐT về 10 số chuẩn Việt Nam để khử trùng ('Một khách - Một hồ sơ').
    Nếu SĐT từ Sàn TMĐT (Shopee/TikTok) bị che dấu '*' (VD: '090****123', '******89')
    hoặc không phải SĐT thật -> Băm SHA-1 tổ hợp (external_ref + full_name + raw_phone) để:
      1. Phân biệt rõ nguồn sàn (SP / TT) và không bao giờ đụng độ ngẫu nhiên giữa 2 người
         (kể cả khi dữ liệu test copy-paste trùng SĐT che và trùng buyer_user_id nhưng khác tên).
      2. Cùng 1 khách hàng trên sàn đó mua lại lần 2 (hoặc khi retry đơn) vẫn ra đúng 1 mã cố định (Idempotent).
    """
    raw = (phone or "").strip()
    if "*" not in raw:
        clean_vn = extract_phone(raw)
        if clean_vn:
            return clean_vn

    # Xác định tiền tố nguồn kênh (SP: Shopee, TT: TikTok, MK: Khác)
    ref_clean = (external_ref or uuid.uuid4().hex).strip().lower()
    if ref_clean.startswith("shopee"):
        ch_tag = "SP"
    elif ref_clean.startswith("tiktok"):
        ch_tag = "TT"
    else:
        ch_tag = "MK"

    name_clean = (full_name or "").strip().lower()
    seed = f"{ref_clean}|{name_clean}|{raw}"
    hash_hex = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:9].upper()

    # Giữ 3 số cuối của SĐT bị che (nếu có) để nhân viên dễ đối chiếu bằng mắt, tổng độ dài <= 20 ký tự
    digits_tail = re.sub(r"\D", "", raw)[-3:] or "000"
    return f"{ch_tag}*{digits_tail}#{hash_hex}"[:20]


def resolve_standard_sku(source_channel: str, source_sku: str, cur=None) -> str:
    """
    Quy tắc nghiệp vụ #2: 'Một sản phẩm - Một mã SKU chuẩn duy nhất'.
    1. Tra bảng `sku_mappings` theo cặp (source_channel, source_sku).
    2. Nếu chưa khai báo trong DB, tự động bóc tiền tố sàn (SP_, TT_, SHOPEE_, TIKTOK_)
       và chuẩn hóa dấu '_' -> '-' để đối chiếu với PRODUCT_CATALOG.
    """
    raw_sku = (source_sku or "").strip()
    if not raw_sku:
        return "AW-HOOD-WWLH-L"

    channel_clean = (source_channel or "landing_page").strip().lower()

    # 1. Tra cứu trong bảng sku_mappings (nếu DB đang kết nối)
    def _lookup_db(db_cur) -> Optional[str]:
        db_cur.execute(
            """
            SELECT standard_sku
            FROM sku_mappings
            WHERE source_channel = %s AND UPPER(source_sku) = UPPER(%s)
            LIMIT 1;
            """,
            (channel_clean, raw_sku)
        )
        row = db_cur.fetchone()
        return row["standard_sku"] if row else None

    try:
        if cur is not None:
            mapped = _lookup_db(cur)
            if mapped:
                return mapped
        else:
            with get_db() as new_cur:
                mapped = _lookup_db(new_cur)
                if mapped:
                    return mapped
    except Exception:
        # Fallback về chuẩn hóa trên bộ nhớ nếu chạy test không bật DB
        pass

    # 2. Chuẩn hóa tiền tố sàn (SP_, TT_, SHOPEE_, TIKTOK_) trên bộ nhớ
    upper_sku = raw_sku.upper().replace("_", "-")
    for prefix in ("SHOPEE-", "TIKTOK-", "SP-", "TT-"):
        if upper_sku.startswith(prefix):
            candidate = upper_sku[len(prefix):]
            if candidate in PRODUCT_CATALOG:
                return candidate

    if upper_sku in PRODUCT_CATALOG:
        return upper_sku

    return raw_sku.upper()


def get_or_create_customer(
    phone: str,
    full_name: str,
    address: str,
    city: str,
    external_ref: Optional[str] = None
) -> int:
    """
    Quy tắc nghiệp vụ: 'Một khách hàng - Một hồ sơ duy nhất' (Dedup theo SĐT).
    - Nếu SĐT thật 10 số đã có trong DB: Cập nhật địa chỉ mới nhất.
    - Nếu SĐT bị sàn Shopee/TikTok che ('090****123'): Tách riêng theo external_ref để không gộp nhầm khách.
    """
    safe_phone = normalize_or_isolate_phone(phone, external_ref=external_ref, full_name=full_name)

    with get_db() as cur:
        cur.execute("SELECT id, full_name FROM customers WHERE phone = %s;", (safe_phone,))
        existing = cur.fetchone()

        if existing:
            # Khách quen: Chỉ cập nhật địa chỉ/tên mới nếu hợp lệ (không ghi đè bằng "Chưa rõ" hoặc tên tạm)
            valid_name = full_name if (full_name and "Khách " not in full_name) else None
            valid_addr = address if (address and "Chưa rõ" not in address) else None
            valid_city = city if (city and "Chưa rõ" not in city) else None
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
                (valid_name, valid_addr, valid_city, existing["id"])
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
                (safe_phone, full_name, address, city)
            )
            new_cust = cur.fetchone()
            return new_cust["id"]

def link_customer_identity(customer_id: int, channel: str, identity_value: str) -> None:
    """
    Ánh xạ tài khoản mạng xã hội (PSID Facebook, User ID Zalo) với customer_iad.
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

def save_chat_message(
    conversation_id: int,
    sender_type: str,
    content: str,
    has_extracted_order: bool = False,
    external_message_id: Optional[str] = None
) -> int:
    """
    Lưu nội dung tin nhắn vào bảng messages (Cột 2 giao diện Chat).
    sender_type: 'customer' hoặc 'shop'
    Chống nhân đôi tin nhắn khi retry nhờ ON CONFLICT (conversation_id, external_message_id).
    """
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO messages (conversation_id, sender_type, content, has_extracted_order, external_message_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (conversation_id, external_message_id) DO NOTHING
            RETURNING id;
            """,
            (conversation_id, sender_type, content, has_extracted_order, external_message_id)
        )
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            "SELECT id FROM messages WHERE conversation_id = %s AND external_message_id = %s LIMIT 1;",
            (conversation_id, external_message_id)
        )
        existing = cur.fetchone()
        return existing["id"] if existing else 0


def get_recent_customer_messages(conversation_id: int, limit: int = 6) -> list:
    """
    Lấy danh sách các tin nhắn gần nhất của khách hàng trong cùng hội thoại
    để tổng hợp ngữ cảnh nhiều tin nhắn (Multi-turn context).
    """
    with get_db() as cur:
        cur.execute(
            """
            SELECT content
            FROM messages
            WHERE conversation_id = %s AND sender_type = 'customer' AND content IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT %s;
            """,
            (conversation_id, limit)
        )
        rows = cur.fetchall()
        # Đảo ngược để theo thứ tự thời gian từ cũ -> mới
        return [r["content"] for r in reversed(rows)]

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
    # Chặn đơn chốt tự động ('processing') nhưng không có sản phẩm nào
    if status == "processing" and (not items or len(items) == 0):
        raise ValueError(f"EMPTY_ORDER_ITEMS: Đơn hàng {source_channel}:{source_order_id} không có sản phẩm nào")

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

        # 2. Tạo các dòng chi tiết sản phẩm (order_items) sau khi quy đổi SKU chuẩn qua sku_mappings (Market-1)
        for item in items:
            raw_sku = (item.get("sku") or item.get("model_sku") or item.get("seller_sku") or "").strip()
            if not raw_sku and status == "processing":
                raise ValueError(f"MISSING_SKU: Dòng sản phẩm trong đơn {source_order_id} bị thiếu mã SKU")

            std_sku = resolve_standard_sku(source_channel, raw_sku or "AW-HOOD-WWLH-L", cur=cur)
            catalog_meta = get_product_by_sku(std_sku)

            # Đối với đơn tự động đẩy kho ('processing' từ Landing Page / Shopee / TikTok), bắt buộc SKU phải hợp lệ trong Catalog chuẩn
            if status == "processing" and not catalog_meta:
                raise ValueError(
                    f"UNMAPPED_SKU: Mã SKU '{raw_sku}' (quy đổi: '{std_sku}') từ kênh '{source_channel}' "
                    f"chưa có trong Danh mục chuẩn / bảng sku_mappings"
                )

            raw_name = item.get("product_name") or item.get("name") or item.get("item_name")
            if catalog_meta and (not raw_name or "Gợi ý mặc định" not in raw_name):
                final_name = catalog_meta["name"]
            else:
                final_name = raw_name or f"Sản phẩm {std_sku}"

            raw_qty = (
                item["quantity"]
                if "quantity" in item and item["quantity"] is not None
                else (
                    item["model_quantity_purchased"]
                    if "model_quantity_purchased" in item and item["model_quantity_purchased"] is not None
                    else 1
                )
            )
            qty = int(raw_qty)
            if qty <= 0:
                raise ValueError(f"INVALID_QUANTITY: Số lượng sản phẩm '{std_sku}' phải lớn hơn 0 (nhận: {qty})")

            raw_price = float(item.get("price") or item.get("unit_price") or 0.0)
            if catalog_meta and (raw_price <= 0 or source_channel == "landing_page"):
                final_price = float(catalog_meta["price"])
            else:
                final_price = raw_price if raw_price > 0 else (float(catalog_meta["price"]) if catalog_meta else 0.0)

            cur.execute(
                """
                INSERT INTO order_items (order_id, sku, product_name, quantity, price)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (order_id, std_sku, final_name, qty, final_price)
            )

        # 3. Luôn tính lại orders.total_amount trực tiếp từ SUM(quantity * price) của order_items (Market-2 / P0-4)
        cur.execute(
            "SELECT COALESCE(SUM(quantity * price), 0) AS real_total FROM order_items WHERE order_id = %s;",
            (order_id,)
        )
        sum_row = cur.fetchone()
        computed_total = float(sum_row["real_total"]) if sum_row else float(total_amount or 0.0)
        cur.execute(
            "UPDATE orders SET total_amount = %s WHERE id = %s;",
            (computed_total, order_id)
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

        # 1. Cập nhật order_items trước nếu tin mới có sản phẩm cụ thể (không phải gợi ý mặc định)
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

        # 2. Luôn tính lại total_amount trực tiếp từ bảng order_items để đảm bảo khớp 100% (Fix P0-4)
        cur.execute(
            "SELECT COALESCE(SUM(quantity * price), 0) AS real_total FROM order_items WHERE order_id = %s;",
            (order_id,)
        )
        sum_row = cur.fetchone()
        new_total = float(sum_row["real_total"]) if sum_row else float(cur_order["total_amount"])

        # 3. Cập nhật bảng orders
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

        return cur_order["order_code"]

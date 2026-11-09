"""
Marketplace Order Handler (Shopee & TikTok Shop)
================================================
Xử lý đơn hàng từ các sàn TMĐT (Shopee, TikTok Shop):
1. Hỗ trợ cả định dạng chuẩn hóa (Canonical Payload) lẫn JSON nguyên bản của Shopee / TikTok.
2. Bảo vệ hồ sơ khách hàng khi SĐT bị sàn ẩn một phần (`090****123`).
3. Tự động quy đổi mã SKU sàn (`model_sku` / `seller_sku`) về mã SKU chuẩn nội bộ qua bảng `sku_mappings`.
4. Lưu Tầng Silver (`status = 'processing'`) và tự động đẩy thẳng sang ShopTrack (`POST /api/v1/orders`).
"""
from typing import Dict, Any, List
from app.services.bronze_service import update_bronze_status
from app.services.silver_service import (
    get_or_create_customer,
    link_customer_identity,
    create_silver_order,
)
from app.services.chat_extractor import extract_phone
from app.services.shoptrack_service import push_order_to_shoptrack


def _extract_marketplace_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa linh hoạt dữ liệu đầu vào từ Shopee / TikTok Shop:
    Chấp nhận cả cấu trúc đã chuẩn hóa (`customer`, `items`) lẫn cấu trúc gốc của Shopee (`recipient_address`, `item_list`)
    hoặc TikTok Shop (`recipient_address`, `line_items`).
    """
    source_channel = (data.get("source_channel") or "shopee").strip().lower()
    source_order_id = (
        data.get("source_order_id")
        or data.get("order_sn")
        or data.get("order_id")
        or "MKT_UNKNOWN"
    )

    cust = data.get("customer") or data.get("recipient_address") or {}
    buyer_name = (
        cust.get("name")
        or cust.get("full_name")
        or data.get("buyer_username")
        or f"Khách {source_channel.capitalize()}"
    )
    raw_phone = str(
        cust.get("phone")
        or cust.get("phone_number")
        or data.get("buyer_phone")
        or "MASKED"
    ).strip()
    # Nếu SĐT không bị che '*', chuẩn hóa về dạng 09xxxxxxxx (10 số)
    clean_phone = extract_phone(raw_phone) if "*" not in raw_phone else None
    buyer_phone = clean_phone or raw_phone

    buyer_address = (
        cust.get("address")
        or cust.get("full_address")
        or cust.get("street")
        or "Địa chỉ Sàn TMĐT"
    )
    buyer_city = (
        cust.get("city")
        or cust.get("state")
        or cust.get("region")
        or cust.get("district")
        or "Hồ Chí Minh"
    )
    buyer_user_id = str(
        data.get("buyer_user_id")
        or cust.get("user_id")
        or source_order_id
    )

    raw_items: List[Dict[str, Any]] = (
        data.get("items")
        or data.get("item_list")
        or data.get("line_items")
        or []
    )

    if not raw_items:
        raise ValueError(f"EMPTY_MARKETPLACE_ITEMS: Đơn hàng {source_channel}:{source_order_id} không có mặt hàng nào")

    normalized_items = []
    for it in raw_items:
        sku = (
            it.get("sku")
            or it.get("model_sku")
            or it.get("seller_sku")
            or it.get("item_sku")
            or ""
        ).strip()
        if not sku:
            raise ValueError(f"MISSING_MARKETPLACE_SKU: Dòng hàng trong đơn {source_order_id} bị rỗng mã SKU")

        name = (
            it.get("name")
            or it.get("product_name")
            or it.get("item_name")
            or f"Sản phẩm {sku}"
        )
        raw_qty = (
            it["quantity"]
            if "quantity" in it and it["quantity"] is not None
            else (
                it["model_quantity_purchased"]
                if "model_quantity_purchased" in it and it["model_quantity_purchased"] is not None
                else 1
            )
        )
        qty = int(raw_qty)
        if qty <= 0:
            raise ValueError(f"INVALID_MARKETPLACE_QTY: Số lượng của SKU '{sku}' không hợp lệ ({qty})")

        price = float(
            it.get("unit_price")
            or it.get("price")
            or it.get("model_discounted_price")
            or it.get("sale_price")
            or 0.0
        )
        normalized_items.append({
            "sku": sku,
            "name": name,
            "quantity": qty,
            "price": price,
            "unit_price": price,
        })

    return {
        "source_channel": source_channel,
        "source_order_id": str(source_order_id),
        "buyer_user_id": buyer_user_id,
        "customer_name": buyer_name,
        "customer_phone": buyer_phone,
        "shipping_address": buyer_address,
        "shipping_city": buyer_city,
        "items": normalized_items,
        "total_amount": float(data.get("total_amount") or 0.0),
        "note": data.get("note") or data.get("message_to_seller") or f"Đơn đồng bộ từ {source_channel.upper()}",
    }


def handle_marketplace_order(data: dict):
    """
    Xử lý đơn hàng từ Shopee hoặc TikTok Shop:
    Chuẩn hóa -> Khử trùng khách -> Map SKU chuẩn -> Lưu Silver ('processing') -> Đẩy thẳng ShopTrack.
    """
    raw_order_id = data["raw_order_id"]
    parsed = _extract_marketplace_fields(data)
    channel = parsed["source_channel"]
    source_order_id = parsed["source_order_id"]

    print("\n" + "=" * 70)
    print(f"🛒 [WORKER MARKETPLACE: {channel.upper()}] BAT DAU XU LY DON SAN TMDT")
    print(f"   * Mã đơn sàn:     {source_order_id} (Bronze #{raw_order_id})")
    print(f"   * Khách hàng:     {parsed['customer_name']} - SĐT: {parsed['customer_phone']}")
    print(f"   * Địa chỉ:        {parsed['shipping_address']}, {parsed['shipping_city']}")
    print(f"   * Số mặt hàng:    {len(parsed['items'])} items")

    # 1. Khử trùng khách hàng (An toàn với cả SĐT thật và SĐT bị sàn ẩn '090****123')
    customer_id = get_or_create_customer(
        phone=parsed["customer_phone"],
        full_name=parsed["customer_name"],
        address=parsed["shipping_address"],
        city=parsed["shipping_city"],
        external_ref=f"{channel}_{parsed['buyer_user_id']}"
    )
    link_customer_identity(
        customer_id=customer_id,
        channel=channel,
        identity_value=parsed["buyer_user_id"]
    )
    print(f"   [+] Định danh khách hàng thành công -> Customer ID #{customer_id}")

    # 2. Tạo đơn chuẩn hóa ở Tầng Silver (Tự động quy đổi sku_mappings & tính chuẩn total_amount)
    order_code = create_silver_order(
        raw_order_id=raw_order_id,
        source_channel=channel,
        source_order_id=source_order_id,
        customer_id=customer_id,
        shipping_name=parsed["customer_name"],
        shipping_phone=parsed["customer_phone"],
        shipping_address=parsed["shipping_address"],
        shipping_city=parsed["shipping_city"],
        items=parsed["items"],
        total_amount=parsed["total_amount"],
        status="processing",
        note=parsed["note"]
    )
    print(f"   [+] Đã chuẩn hóa Tầng Silver: Mã đơn {order_code} (Status: 'processing')")

    # 3. Tự động đẩy thẳng sang ShopTrack & ghi sync_audit_logs
    push_order_to_shoptrack(order_code)

    # 4. Cập nhật Tầng Bronze -> 'processed'
    update_bronze_status(raw_order_id, "processed")
    print(f"   [+] Đã cập nhật Tầng Bronze (raw_orders #{raw_order_id}) -> 'processed'")
    print("=" * 70 + "\n")


"""
Bộ Kiểm thử Tự động Kịch bản Phản biện (/grill-idea) cho Nhóm 2 (Shopee, TikTok & ShopTrack)
===========================================================================================
Chạy trực tiếp bằng lệnh:
    python ptit-gomdon-middleware/middleware/tests/test_nhom2_marketplace.py
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

# Thêm thư mục middleware vào sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MIDDLEWARE_DIR = os.path.dirname(CURRENT_DIR)
if MIDDLEWARE_DIR not in sys.path:
    sys.path.insert(0, MIDDLEWARE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.silver_service import (
    resolve_standard_sku,
    normalize_or_isolate_phone,
    create_silver_order,
)
from app.workers.handlers.marketplace_handler import _extract_marketplace_fields
from app.workers.order_consumer import process_order_message
from mock_shoptrack import create_order, CreateOrderPayload, DB_ORDERS, SEEN_IDEMPOTENCY_KEYS


def run_all_tests():
    print("=" * 78)
    print("🔥 CHẠY BỘ KIỂM THỬ 8 KỊCH BẢN PHẢN BIỆN (/GRILL-IDEA) — NHÓM 2 (SHOPEE/TIKTOK)")
    print("=" * 78)

    # 1. Kịch bản 1: Quy đổi SKU đa biến thể Sàn TMĐT
    assert resolve_standard_sku("shopee", "SP_AW_HOOD_WCH_XXL") == "AW-HOOD-WCH-XXL"
    assert resolve_standard_sku("shopee", "SHOPEE_AW_SHIRT_WUTJ_M") == "AW-SHIRT-WUTJ-M"
    assert resolve_standard_sku("tiktok", "TT_AW_LS_WRLL_S") == "AW-LS-WRLL-S"
    assert resolve_standard_sku("tiktok", "TIKTOK_AW_JKT_TLSJ_XL") == "AW-JKT-TLSJ-XL"
    print("✅ [PASS] Kịch bản 1: Quy đổi SKU đa biến thể Shopee/TikTok -> SKU chuẩn Alan Walker")

    # 2. Kịch bản 2: Chống đụng độ SĐT bị che (kể cả trùng đuôi buyer_user_id giữa Shopee & TikTok)
    p_sp_1 = normalize_or_isolate_phone("090****123", external_ref="shopee_USER_12345678")
    p_tt_1 = normalize_or_isolate_phone("090****123", external_ref="tiktok_USER_12345678")
    p_sp_1_repeat = normalize_or_isolate_phone("090****123", external_ref="shopee_USER_12345678")
    p_real = normalize_or_isolate_phone("+84 905 111 222", external_ref="shopee_USER_999")
    assert p_sp_1 != p_tt_1, f"Trùng khóa giữa Shopee và TikTok: {p_sp_1} == {p_tt_1}"
    assert p_sp_1 == p_sp_1_repeat, "Cùng 1 khách mua lần 2 phải ra cùng khóa định danh"
    assert p_real == "0905111222"
    print(f"✅ [PASS] Kịch bản 2: Khóa SĐT ẩn SHA-1 an toàn ({p_sp_1} != {p_tt_1}) & Idempotent khi mua lại")

    # 3. Kịch bản 3: Bóc tách JSON gốc Shopee & TikTok
    sp_parsed = _extract_marketplace_fields({
        "source_channel": "shopee",
        "order_sn": "SP261107001",
        "buyer_user_id": "U_SP_01",
        "recipient_address": {
            "name": "Lê Văn C",
            "phone": "+84 912 345 678",
            "full_address": "10 Trần Phú",
            "city": "Hà Nội",
        },
        "item_list": [
            {
                "model_sku": "SP_AW_HOOD_WCH_XL",
                "model_quantity_purchased": 2,
                "model_discounted_price": 264000,
            }
        ],
    })
    tt_parsed = _extract_marketplace_fields({
        "source_channel": "tiktok",
        "order_id": "TT261107002",
        "recipient_address": {
            "name": "Phạm Thị D",
            "phone_number": "098****777",
            "full_address": "20 Nguyễn Văn Linh",
            "region": "Đà Nẵng",
        },
        "line_items": [
            {
                "seller_sku": "TT_AW_JKT_CLV1_L",
                "quantity": 1,
                "sale_price": 1165000,
            }
        ],
    })
    assert sp_parsed["customer_phone"] == "0912345678" and sp_parsed["items"][0]["quantity"] == 2
    assert tt_parsed["customer_phone"] == "098****777" and tt_parsed["shipping_city"] == "Đà Nẵng"
    print("✅ [PASS] Kịch bản 3: Chuẩn hóa đúng cả JSON gốc Shopee (item_list) & TikTok (line_items)")

    # 4. Kịch bản 4: Chặn đơn rỗng sản phẩm / thiếu SKU / số lượng <= 0 (kể cả bẫy falsy quantity=0)
    for bad_payload, expected_err in [
        ({"source_channel": "shopee", "order_sn": "BAD1", "item_list": []}, "EMPTY_MARKETPLACE_ITEMS"),
        (
            {"source_channel": "shopee", "order_sn": "BAD2", "item_list": [{"model_sku": "   ", "model_quantity_purchased": 1}]},
            "MISSING_MARKETPLACE_SKU",
        ),
        (
            {"source_channel": "tiktok", "order_id": "BAD3", "line_items": [{"seller_sku": "AW-HOOD-WCH-L", "quantity": 0}]},
            "INVALID_MARKETPLACE_QTY",
        ),
    ]:
        try:
            _extract_marketplace_fields(bad_payload)
            raise AssertionError(f"Phải chặn {expected_err}")
        except ValueError as e:
            assert expected_err in str(e), f"Sai mã lỗi: {e}"
    print("✅ [PASS] Kịch bản 4: Chặn đứng đơn rỗng items, rỗng SKU hoặc số lượng <= 0 (kể cả quantity=0)")

    # 5 & 6. Kịch bản 5 & 6: Kiểm thử create_silver_order chặn UNMAPPED_SKU và tự tính lại total_amount
    mock_cur = MagicMock()
    inserted_items = []
    updated_totals = []

    def side_effect_exec(sql, params=None):
        if "INSERT INTO orders" in sql:
            mock_cur.fetchone.return_value = {"id": 99, "order_code": params[0]}
        elif "SELECT standard_sku" in sql:
            mock_cur.fetchone.return_value = None
        elif "INSERT INTO order_items" in sql:
            inserted_items.append(params)
        elif "SELECT COALESCE(SUM(quantity * price)" in sql:
            total = sum(x[3] * x[4] for x in inserted_items)
            mock_cur.fetchone.return_value = {"real_total": total}
        elif "UPDATE orders SET total_amount" in sql:
            updated_totals.append(params[0])

    mock_cur.execute.side_effect = side_effect_exec
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_cur

    with patch("app.services.silver_service.get_db", return_value=mock_cm):
        # 5: UNMAPPED_SKU phải bị chặn
        try:
            create_silver_order(
                raw_order_id=1,
                source_channel="shopee",
                source_order_id="SP_UNMAPPED",
                customer_id=1,
                shipping_name="A",
                shipping_phone="0912345678",
                shipping_address="HN",
                shipping_city="Hà Nội",
                items=[{"sku": "SP_MA_AO_LA_999", "quantity": 1, "price": 100000}],
                total_amount=100000,
                status="processing",
            )
            raise AssertionError("Phải chặn UNMAPPED_SKU")
        except ValueError as e:
            assert "UNMAPPED_SKU" in str(e)
        print("✅ [PASS] Kịch bản 5: Chặn mã SKU lạ chưa map (UNMAPPED_SKU) không cho lọt sang ShopTrack")

        # 6: Tự tính lại total_amount bất chấp client/sàn truyền sai total_amount = 1000 hoặc price = -50
        inserted_items.clear()
        updated_totals.clear()
        create_silver_order(
            raw_order_id=2,
            source_channel="shopee",
            source_order_id="SP_OK_01",
            customer_id=1,
            shipping_name="A",
            shipping_phone="0912345678",
            shipping_address="HN",
            shipping_city="Hà Nội",
            items=[
                {"sku": "SP_AW_HOOD_WCH_XXL", "quantity": 2, "price": -50},
                {"sku": "SHOPEE_AW_SHIRT_WUTJ_L", "quantity": 1, "price": 0},
            ],
            total_amount=1000,
            status="processing",
        )
        assert updated_totals[-1] == 1164000.0, f"Sai tổng tiền: {updated_totals[-1]}"
        print(
            f"✅ [PASS] Kịch bản 6: Tự động quy đổi SKU, sửa giá <=0 về giá Catalog & tính chuẩn total_amount = {updated_totals[-1]:,.0f} VND"
        )

    # 7. Kịch bản 7: ShopTrack Mock Idempotency & Multi-item
    DB_ORDERS.clear()
    SEEN_IDEMPOTENCY_KEYS.clear()
    payload_st = CreateOrderPayload(
        source_channel="shopee",
        source_order_id="SP_OK_01",
        customer_name="Nguyễn Văn A",
        customer_phone="0912345678",
        shipping_address="122 Hoàng Quốc Việt",
        shipping_city="Hà Nội",
        items=[
            {"sku": "AW-HOOD-WCH-XXL", "quantity": 2, "price": 264000},
            {"sku": "AW-SHIRT-WUTJ-L", "quantity": 1, "price": 636000},
        ],
        total_amount=1164000,
    )
    r1 = create_order(payload_st, idempotency_key="shopee_SP_OK_01")
    r2 = create_order(payload_st, idempotency_key="shopee_SP_OK_01")
    assert r1["status"] == "success" and r2["status"] == "duplicate_prevented"
    assert r1["order_id"] == r2["order_id"] and r1["tracking_code"] == r2["tracking_code"]
    assert len(DB_ORDERS) == 1
    print(
        f"✅ [PASS] Kịch bản 7: ShopTrack Idempotency chuẩn xác (Mã đơn: {r1['order_id']}, Vận đơn: {r1['tracking_code']})"
    )

    # 8. Kịch bản 8: Kênh lạ chưa đăng ký ('lazada') phải bị NACK vào DLQ, tuyệt đối không ACK mất đơn
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 777
    with patch("app.workers.order_consumer.update_bronze_status") as mock_upd:
        process_order_message(
            mock_ch,
            mock_method,
            None,
            json.dumps({"raw_order_id": 55, "source_order_id": "LZ_01", "source_channel": "lazada"}).encode(),
        )
        mock_ch.basic_ack.assert_not_called()
        mock_ch.basic_nack.assert_called_once_with(delivery_tag=777, requeue=False)
        mock_upd.assert_called_once()
    print("✅ [PASS] Kịch bản 8: Kênh lạ (lazada) tự động NACK vào DLQ & đánh dấu Bronze failed, không mất đơn!")
    print("=" * 78)
    print("🎉 TẤT CẢ 8/8 KỊCH BẢN PHẢN BIỆN NHÓM 2 ĐỀU VƯỢT QUA 100%!")
    print("=" * 78)


if __name__ == "__main__":
    run_all_tests()


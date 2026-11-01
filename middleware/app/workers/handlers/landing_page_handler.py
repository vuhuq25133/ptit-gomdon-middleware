"""
Landing Page Order Handler
==========================
Xử lý đơn hàng trực tiếp từ Landing Page (Đơn đủ thông tin -> status: 'processing').
"""
from app.services.bronze_service import update_bronze_status
from app.services.silver_service import (
    get_or_create_customer,
    create_silver_order
)


def handle_landing_page_order(data: dict):
    """Xử lý đơn hàng trực tiếp từ Landing Page (Đơn đủ thông tin -> status: 'processing')"""
    raw_order_id = data["raw_order_id"]
    source_order_id = data["source_order_id"]
    cust_data = data["customer"]

    print("\n" + "=" * 70)
    print(f"⚙️  [WORKER LANDING PAGE] BAT DAU XU LY DON HANG")
    print(f"   * Nguồn:          LANDING_PAGE ({source_order_id})")
    print(f"   * Bronze ID:      #{raw_order_id}")
    print(f"   * Khách hàng:     {cust_data['name']} - SĐT: {cust_data['phone']}")
    print(f"   * Địa chỉ:        {cust_data['address']}, {cust_data['city']}")
    print(f"   * Tổng tiền:      {data['total_amount']:,.0f} VND")

    # 1. Khử trùng khách hàng theo SĐT ("Một khách - Một hồ sơ")
    customer_id = get_or_create_customer(
        phone=cust_data["phone"],
        full_name=cust_data["name"],
        address=cust_data["address"],
        city=cust_data["city"]
    )
    print(f"   [+] Khử trùng khách hàng thành công -> Customer ID #{customer_id}")

    # 2. Chuẩn hóa & Lưu trữ vào Tầng Silver (orders + order_items)
    order_code = create_silver_order(
        raw_order_id=raw_order_id,
        source_channel="landing_page",
        source_order_id=source_order_id,
        customer_id=customer_id,
        shipping_name=cust_data["name"],
        shipping_phone=cust_data["phone"],
        shipping_address=cust_data["address"],
        shipping_city=cust_data["city"],
        items=data["items"],
        total_amount=data["total_amount"],
        status="processing",
        note=data.get("note")
    )
    print(f"   [+] Đã lưu vào Tầng Silver (bảng orders): Mã đơn {order_code} (Status: 'processing')")

    # 3. Cập nhật Tầng Bronze -> 'processed'
    update_bronze_status(raw_order_id, "processed")
    print(f"   [+] Đã cập nhật Tầng Bronze (raw_orders #{raw_order_id}) -> 'processed'")
    print("=" * 70 + "\n")

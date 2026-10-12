import json
import sys
import time

# Đảm bảo UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.core.config import settings
from app.core.rabbitmq_client import get_rabbitmq_connection, init_rabbitmq_topology
from app.services.bronze_service import update_bronze_status
from app.services.silver_service import get_or_create_customer, create_silver_order

def process_order_message(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        raw_order_id = data["raw_order_id"]
        source_order_id = data["source_order_id"]
        cust_data = data["customer"]

        print("\n" + "=" * 70)
        print(f"⚙️  [WORKER] BAT DAU XU LY DON HANG TU RABBITMQ QUEUE")
        print(f"   * Nguồn:          {data['source_channel'].upper()} ({source_order_id})")
        print(f"   * Bronze ID:      #{raw_order_id}")
        print(f"   * Khách hàng:     {cust_data['name']} - SĐT: {cust_data['phone']}")
        print(f"   * Địa chỉ:        {cust_data['address']}, {cust_data['city']}")
        print(f"   * Tổng tiền:      {data['total_amount']:,.0f} VND")

        # 1. BƯỚC 1: Khử trùng khách hàng theo SĐT ("Một khách - Một hồ sơ")
        customer_id = get_or_create_customer(
            phone=cust_data["phone"],
            full_name=cust_data["name"],
            address=cust_data["address"],
            city=cust_data["city"]
        )
        print(f"   [+] Khử trùng khách hàng thành công -> Customer ID #{customer_id}")

        # 2. BƯỚC 2: Chuẩn hóa & Lưu trữ vào Tầng Silver (orders + order_items)
        order_code = create_silver_order(
            raw_order_id=raw_order_id,
            source_channel=data["source_channel"],
            source_order_id=source_order_id,
            customer_id=customer_id,
            shipping_name=cust_data["name"],
            shipping_phone=cust_data["phone"],
            shipping_address=cust_data["address"],
            shipping_city=cust_data["city"],
            items=data["items"],
            total_amount=data["total_amount"],
            note=data.get("note")
        )
        print(f"   [+] Đã lưu vào Tầng Silver (bảng orders): Mã đơn {order_code}")

        # 3. BƯỚC 3: Cập nhật trạng thái Tầng Bronze là đã xử lý
        update_bronze_status(raw_order_id, "processed")
        print(f"   [+] Đã cập nhật Tầng Bronze (raw_orders #{raw_order_id}) -> 'processed'")

        # (Theo chỉ đạo: Chưa cần đẩy đơn sang ShopTrack, tập trung hứng và chuẩn hóa dữ liệu kho)
        print(f"   📦 [HOÀN TẤT GOM ĐƠN] Đơn hàng đã nằm an toàn trong CSDL PostgreSQL!")
        print("=" * 70 + "\n")

        # Xác nhận tin nhắn đã xử lý thành công (ACK) để RabbitMQ xóa khỏi hàng đợi
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[-] [WORKER LOI]: {str(e)}")
        # Cập nhật trạng thái lỗi ở tầng Bronze
        if "raw_order_id" in locals():
            update_bronze_status(raw_order_id, "failed", error_message=str(e))
        # NACK không requeue để tránh vòng lặp lỗi vô tận
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def start_worker():
    print("=" * 70)
    print("🚀 [ASYNC WORKER] KHOI DONG TIEN TRINH TIEU THU THONG DIEP RABBITMQ...")
    print(f"   * Exchange: {settings.EXCHANGE_NAME}")
    print(f"   * Queue:    {settings.QUEUE_NAME}")
    print("=" * 70)

    # Đảm bảo Exchange và Queue đã tồn tại
    init_rabbitmq_topology()

    conn = get_rabbitmq_connection()
    ch = conn.channel()

    # Giới hạn mỗi lần worker chỉ nhận 1 message để xử lý tuần tự chuẩn xác
    ch.basic_qos(prefetch_count=1)

    ch.basic_consume(
        queue=settings.QUEUE_NAME,
        on_message_callback=process_order_message,
        auto_ack=False
    )

    print("[*] Worker dang lang nghe don hang moi... (Bam Ctrl + C de thoat)\n")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        print("\n[*] Worker da dung hoat dong.")
        ch.stop_consuming()
        conn.close()

if __name__ == "__main__":
    start_worker()

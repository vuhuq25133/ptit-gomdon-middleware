"""
Async Order Consumer (RabbitMQ Worker Dispatcher)
==================================================
Tiến trình ngầm (Worker) tiêu thụ thông điệp từ hàng đợi 'orders.inbound.queue'.
Hoạt động như một Bộ điều phối (Dispatcher / Router) độc lập:
- Tiếp nhận message từ RabbitMQ.
- Phân luồng sang Handler tương ứng theo `source_channel`:
    + 'landing_page' -> handle_landing_page_order
    + 'facebook'     -> handle_facebook_message
    + 'zalo'         -> handle_zalo_message (khi tích hợp)
- Quản lý cơ chế xác nhận (ACK/NACK) và cập nhật trạng thái lỗi ở tầng Bronze.
"""
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

# Import các handlers chuyên biệt theo từng kênh
from app.workers.handlers.landing_page_handler import handle_landing_page_order
from app.workers.handlers.facebook_handler import handle_facebook_message

# Bản đồ đăng ký các bộ xử lý theo kênh bán (Registry Pattern)
CHANNEL_HANDLERS = {
    "landing_page": handle_landing_page_order,
    "facebook": handle_facebook_message,
}

# Cấu hình Retry theo cấp số nhân (Exponential Backoff: 2^0=1s, 2^1=2s, 2^2=4s)
RETRY_DELAYS = [1, 2, 4]


def _sleep_preserving_heartbeat(ch, seconds: float):
    """Nghỉ chờ theo Exponential Backoff nhưng vẫn duy trì nhịp tim (Heartbeat) với RabbitMQ"""
    if hasattr(ch, "connection") and ch.connection and hasattr(ch.connection, "sleep"):
        try:
            ch.connection.sleep(seconds)
            return
        except Exception:
            pass
    time.sleep(seconds)


def process_order_message(ch, method, properties, body):
    """
    Callback xử lý message từ RabbitMQ và phân phối tới Handler tương ứng.
    Tích hợp cơ chế:
    1. Retry Exponential Backoff (1s -> 2s -> 4s) cho các lỗi tạm thời (DB nghẽn, mạng chập chờn).
    2. Chống sập Worker (Safe Bronze Status Update) khi Database mất kết nối hoàn toàn.
    3. Tự động đẩy vào Dead Letter Queue (orders.dlq.queue) qua basic_nack(requeue=False)
       sau khi đã thử lại hết số lần quy định.
    """
    raw_order_id = None
    source_order_id = None
    try:
        data = json.loads(body.decode("utf-8"))
        raw_order_id = data.get("raw_order_id")
        source_order_id = data.get("source_order_id")
        source_channel = data.get("source_channel", "landing_page")

        handler = CHANNEL_HANDLERS.get(source_channel)
        if handler:
            max_attempts = len(RETRY_DELAYS) + 1
            for attempt in range(1, max_attempts + 1):
                try:
                    handler(data)
                    if attempt > 1:
                        print(f"[+] [RETRY THANH CONG] Don {source_order_id} da xu ly thanh cong o lan thu {attempt}!")
                    break
                except Exception as handler_err:
                    if attempt <= len(RETRY_DELAYS):
                        delay = RETRY_DELAYS[attempt - 1]
                        print(
                            f"[!] [RETRY {attempt}/{len(RETRY_DELAYS)}] Loi xu ly don {source_order_id}: {handler_err}. "
                            f"Tu dong thu lai sau {delay}s (Exponential Backoff)..."
                        )
                        _sleep_preserving_heartbeat(ch, delay)
                    else:
                        # Đã hết toàn bộ số lần thử lại (1s -> 2s -> 4s), ném lỗi ra ngoài để chuyển vào DLQ
                        raise handler_err
        else:
            print(f"[-] Kênh chưa được hỗ trợ: {source_channel}")

        # Xác nhận tin nhắn đã xử lý thành công (ACK) để RabbitMQ xóa khỏi hàng đợi chính
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[-] [WORKER LOI NGHIEM TRONG -> CHUYEN VAO DLQ ({settings.DLQ_QUEUE_NAME})]: {str(e)}")
        # Cập nhật trạng thái lỗi ở tầng Bronze (Bọc try-except riêng để tránh sập Worker khi DB chết hẳn)
        if raw_order_id:
            try:
                update_bronze_status(raw_order_id, "failed", error_message=str(e))
            except Exception as db_err:
                print(f"[!] [CANH BAO] Khong the cap nhat trang thai Bronze do DB dang mat ket noi: {db_err}")

        # NACK (requeue=False): Kích hoạt x-dead-letter-exchange đẩy gói tin sang kho an toàn orders.dlq.queue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    """Khởi động tiến trình lắng nghe thông điệp từ RabbitMQ"""
    print("=" * 70)
    print("🚀 [ASYNC WORKER] KHOI DONG TIEN TRINH TIEU THU THONG DIEP RABBITMQ...")
    print(f"   * Exchange: {settings.EXCHANGE_NAME}")
    print(f"   * Queue:    {settings.QUEUE_NAME}")
    print(f"   * Channels: {', '.join(CHANNEL_HANDLERS.keys())}")
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
        print("\n[!] Nhan lenh dung Worker tu nguoi dung. Dang dong ket noi...")
        ch.stop_consuming()
        conn.close()
        print("[+] Worker da dung an toan!")


if __name__ == "__main__":
    start_worker()

import sys
import os

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import get_db_pool
from app.core.rabbitmq_client import init_rabbitmq_topology, replay_dlq_messages
from app.api.inbound import router as inbound_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Gateway Thu thập và Chuẩn hóa dữ liệu Đơn hàng Đa nền tảng (Đồ án PTIT)",
    version="2.0.0"
)

# 1. Mount thư mục static phục vụ giao diện Web Landing Page
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 2. Đăng ký các router tiếp nhận dữ liệu
app.include_router(inbound_router)

@app.on_event("startup")
def on_startup():
    print("[*] Đang kiểm tra và khởi tạo hạ tầng PostgreSQL Pool & RabbitMQ...")
    try:
        get_db_pool()
        print("[+] Hồ chứa kết nối PostgreSQL (ThreadedConnectionPool) đã sẵn sàng!")
    except Exception as e:
        print(f"[-] Cảnh báo: Chưa thể khởi tạo PostgreSQL Pool ({e})")

    try:
        init_rabbitmq_topology()
        print("[+] Hạ tầng RabbitMQ (Exchange & Queue) đã sẵn sàng!")
    except Exception as e:
        print(f"[-] Cảnh báo: Chưa thể khởi tạo RabbitMQ topology ({e})")

@app.get("/")
def index():
    """Tự động chuyển hướng về trang đặt hàng Landing Page"""
    return RedirectResponse(url="/static/landing_page.html")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "2.0.0",
        "lakehouse_status": "connected"
    }


@app.post("/admin/dlq/replay", tags=["Admin - Quản trị Hàng đợi Lỗi (DLQ)"])
def admin_replay_dlq():
    """
    Phục hồi hàng loạt (Batch Replay) toàn bộ các đơn/tin nhắn đang nằm trong kho lỗi
    `orders.dlq.queue` quay trở lại hàng đợi chính `orders.inbound.queue` sau khi khắc phục sự cố.
    """
    result = replay_dlq_messages()
    return {
        "status": "success",
        "message": f"Đã đẩy thành công {result['replayed_count']} gói tin từ DLQ về lại hàng đợi chính!",
        "data": result
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.APP_PORT, reload=True)

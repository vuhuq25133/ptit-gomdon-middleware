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
from app.core.database import get_db_pool, get_db
from app.core.catalog import PRODUCT_CATALOG
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


def ensure_schema_and_catalog():
    """
    Tự động bổ sung cột external_message_id vào bảng `messages` có sẵn
    và nạp danh mục SKU Alan Walker Store vào bảng `sku_mappings` có sẵn
    (cho cả 5 kênh: landing_page, facebook, zalo, shopee, tiktok).
    KHÔNG đẻ thêm bất kỳ bảng mới nào ngoài thiết kế gốc trong init_db.sql.
    """
    with get_db() as cur:
        cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS external_message_id VARCHAR(100);")
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_messages_conv_ext_id') THEN
                    ALTER TABLE messages ADD CONSTRAINT uq_messages_conv_ext_id UNIQUE (conversation_id, external_message_id);
                END IF;
            END $$;
            """
        )
        for sku in PRODUCT_CATALOG.keys():
            # Nạp bảng ánh xạ sku_mappings có sẵn cho cả 5 kênh + biến thể mã sàn Shopee (SP_) & TikTok (TT_)
            for ch in ("landing_page", "facebook", "zalo", "shopee", "tiktok"):
                cur.execute(
                    """
                    INSERT INTO sku_mappings (source_channel, source_sku, standard_sku)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (source_channel, source_sku) DO UPDATE SET standard_sku = EXCLUDED.standard_sku;
                    """,
                    (ch, sku, sku)
                )
            # Bổ sung biến thể mã riêng của sàn (VD: SP_AW_HOOD_WCH_XL, TT_AW_HOOD_WCH_XL)
            sku_underscore = sku.replace("-", "_")
            for alias_sku in (f"SP-{sku}", f"SP_{sku_underscore}", f"SHOPEE_{sku_underscore}"):
                cur.execute(
                    """
                    INSERT INTO sku_mappings (source_channel, source_sku, standard_sku)
                    VALUES ('shopee', %s, %s)
                    ON CONFLICT (source_channel, source_sku) DO UPDATE SET standard_sku = EXCLUDED.standard_sku;
                    """,
                    (alias_sku, sku)
                )
            for alias_sku in (f"TT-{sku}", f"TT_{sku_underscore}", f"TIKTOK_{sku_underscore}"):
                cur.execute(
                    """
                    INSERT INTO sku_mappings (source_channel, source_sku, standard_sku)
                    VALUES ('tiktok', %s, %s)
                    ON CONFLICT (source_channel, source_sku) DO UPDATE SET standard_sku = EXCLUDED.standard_sku;
                    """,
                    (alias_sku, sku)
                )


@app.on_event("startup")
def on_startup():
    print("[*] Đang kiểm tra và khởi tạo hạ tầng PostgreSQL Pool & RabbitMQ...")
    try:
        get_db_pool()
        ensure_schema_and_catalog()
        print(f"[+] Hồ chứa PostgreSQL & Danh mục {len(PRODUCT_CATALOG)} SKU Alan Walker Store đã sẵn sàng!")
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

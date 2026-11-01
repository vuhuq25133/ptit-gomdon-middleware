import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Nạp file .env từ thư mục middleware
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Gom Đơn Đa Nền Tảng")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "StrongPassword@2026")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "gomdon_lakehouse")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "RedisPass@2026")

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "127.0.0.1")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "admin")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "RabbitAdmin@2026")

    # RabbitMQ Topology (Main Queue + Dead Letter Queue)
    EXCHANGE_NAME: str = "orders.exchange"
    QUEUE_NAME: str = "orders.inbound.queue"
    DLX_EXCHANGE_NAME: str = "orders.dlx"
    DLQ_QUEUE_NAME: str = "orders.dlq.queue"

    # ==============================================================================
    # CẤU HÌNH & ROUTING KEY CHO 5 NGUỒN THU THẬP ĐƠN HÀNG (5 INBOUND SOURCES)
    # ==============================================================================
    # Nguồn 1: Kênh Landing Page (Web Form Trực Tiếp - Giai đoạn 1)
    ROUTING_KEY_LANDING: str = "order.landing"

    # Nguồn 2: Kênh Facebook Fanpage (Messenger Webhook - Giai đoạn 2)
    ROUTING_KEY_FACEBOOK_MESSAGE: str = "order.facebook.message"
    FB_VERIFY_TOKEN: str = os.getenv("META_VERIFY_TOKEN", os.getenv("FB_VERIFY_TOKEN", "ptit_webhook_secret_token_2026"))

    # Nguồn 3: Kênh Zalo OA (Official Account Webhook - Giai đoạn 3)
    ROUTING_KEY_ZALO: str = "order.zalo.message"
    ZALO_OA_SECRET_KEY: str = os.getenv("ZALO_OA_SECRET_KEY", "zalo_oa_mock_secret_2026")

    # Nguồn 4: Kênh Shopee (Sàn TMĐT Open API - Giai đoạn 4)
    ROUTING_KEY_SHOPEE: str = "order.shopee"

    # Nguồn 5: Kênh TikTok Shop (Sàn TMĐT Partner API - Giai đoạn 4)
    ROUTING_KEY_TIKTOK: str = "order.tiktok"

settings = Settings()

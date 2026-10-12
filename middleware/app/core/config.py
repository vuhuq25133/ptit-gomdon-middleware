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

    EXCHANGE_NAME: str = "orders.exchange"
    QUEUE_NAME: str = "orders.inbound.queue"
    ROUTING_KEY_LANDING: str = "order.landing"

settings = Settings()

import json
import pika
from app.core.config import settings

def get_rabbitmq_connection():
    creds = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=creds,
        heartbeat=60
    )
    return pika.BlockingConnection(params)

def init_rabbitmq_topology():
    """Khởi tạo Exchange và Queue trên RabbitMQ nếu chưa có"""
    conn = get_rabbitmq_connection()
    ch = conn.channel()

    # 1. Khởi tạo Direct/Topic Exchange
    ch.exchange_declare(
        exchange=settings.EXCHANGE_NAME,
        exchange_type="topic",
        durable=True
    )

    # 2. Khởi tạo Queue bền vững (durable)
    ch.queue_declare(
        queue=settings.QUEUE_NAME,
        durable=True
    )

    # 3. Bind Queue với Exchange theo routing pattern order.*
    ch.queue_bind(
        queue=settings.QUEUE_NAME,
        exchange=settings.EXCHANGE_NAME,
        routing_key="order.*"
    )

    conn.close()

def publish_order_event(routing_key: str, message_dict: dict) -> bool:
    """Publish thông điệp đơn hàng vào RabbitMQ Exchange"""
    conn = get_rabbitmq_connection()
    ch = conn.channel()

    body = json.dumps(message_dict, ensure_ascii=False).encode("utf-8")
    properties = pika.BasicProperties(
        delivery_mode=pika.DeliveryMode.Persistent, # Đảm bảo tin nhắn lưu vào đĩa (durable)
        content_type="application/json"
    )

    ch.basic_publish(
        exchange=settings.EXCHANGE_NAME,
        routing_key=routing_key,
        body=body,
        properties=properties
    )

    conn.close()
    return True

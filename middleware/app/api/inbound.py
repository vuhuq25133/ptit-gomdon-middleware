import time
import uuid
from fastapi import APIRouter, HTTPException, status
from app.schemas.order import LandingPageOrderIn, InboundResponse
from app.core.redis_client import check_and_set_dedup
from app.core.rabbitmq_client import publish_order_event
from app.services.bronze_service import save_to_bronze

router = APIRouter(prefix="/inbound", tags=["Inbound Ingestion"])

@router.post("/landing-page", response_model=InboundResponse)
async def receive_landing_page_order(order: LandingPageOrderIn):
    start_time = time.time()

    # 1. Khóa chống spam / click đúp 30 giây bằng Redis SETNX
    dedup_key = f"{order.phone}_{order.sku}"
    is_allowed = check_and_set_dedup(dedup_key, expire_seconds=30)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn vừa gửi đơn hàng tương tự cách đây ít giây. Vui lòng đợi 30 giây trước khi đặt lại!"
        )

    # 2. Sinh mã nguồn đơn Landing Page
    source_order_id = f"LP_{uuid.uuid4().hex[:8].upper()}"
    raw_dict = order.model_dump()

    # 3. Lưu trữ Tầng Bronze (PostgreSQL raw_orders) - Không bao giờ mất dữ liệu gốc
    try:
        raw_order_id = save_to_bronze(
            source_channel="landing_page",
            source_order_id=source_order_id,
            raw_payload=raw_dict
        )
    except Exception as e:
        print(f"[-] [LOI LUU BRONZE]: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi lưu trữ kho Bronze: {str(e)}"
        )

    # 4. Đóng gói và bắn message vào RabbitMQ (Exchange: orders.exchange, Key: order.landing)
    message_payload = {
        "raw_order_id": raw_order_id,
        "source_channel": "landing_page",
        "source_order_id": source_order_id,
        "customer": {
            "name": order.full_name,
            "phone": order.phone,
            "address": order.address,
            "city": order.city
        },
        "items": [
            {
                "sku": order.sku,
                "quantity": order.quantity,
                "price": order.unit_price
            }
        ],
        "total_amount": order.unit_price * order.quantity,
        "note": order.note,
        "ingested_at": time.time()
    }

    try:
        publish_order_event(
            routing_key="order.landing",
            message_dict=message_payload
        )
    except Exception as e:
        print(f"[-] [LOI BAN RABBITMQ]: {str(e)}")
        # Ngay cả khi RabbitMQ lỗi, đơn vẫn an toàn nằm ở bảng raw_orders (Bronze)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi đẩy vào hàng đợi RabbitMQ: {str(e)}"
        )

    duration_ms = round((time.time() - start_time) * 1000, 2)

    print("\n" + "=" * 70)
    print(f"[GATEWAY INGESTION] TIEP NHAN THANH CONG (Thoi gian: {duration_ms} ms)")
    print(f"   * Ma don nguon:    {source_order_id}")
    print(f"   * Bronze Record:   ID #{raw_order_id} (Bang raw_orders)")
    print(f"   * Khach hang:      {order.full_name} ({order.phone})")
    print(f"   * San pham:        {order.sku} x {order.quantity}")
    print(f"   * RabbitMQ Queue:  orders.inbound.queue (Routing key: order.landing)")
    print("=" * 70 + "\n")

    return InboundResponse(
        status="success",
        message="Đơn hàng đã được lưu kho Bronze và đưa vào hàng đợi xử lý ngầm",
        source_order_id=source_order_id,
        raw_order_id=raw_order_id,
        duration_ms=duration_ms
    )

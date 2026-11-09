"""
Landing Page Ingestion Router (Alan Walker Store Checkout)
==========================================================
Tiếp nhận đơn hàng trực tiếp từ Landing Page (REST API):
- GET  /inbound/landing-page/catalog : Trả về danh mục 58 mẫu áo Alan Walker (4 loại x 5 size = 290 SKU).
- POST /inbound/landing-page         : Xác thực SKU & giá chuẩn từ Catalog, lưu Bronze và đẩy RabbitMQ.
"""
import time
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.catalog import get_product_by_sku, get_catalog_summary
from app.core.redis_client import check_and_set_dedup
from app.core.rabbitmq_client import publish_order_event
from app.services.bronze_service import save_to_bronze
from app.schemas.order import LandingPageOrderIn, InboundResponse

router = APIRouter(prefix="/landing-page", tags=["Landing Page Ingestion"])


@router.get(
    "/catalog",
    summary="Lấy danh mục sản phẩm Alan Walker Store (58 mẫu x 5 size = 290 SKU)"
)
def get_landing_catalog():
    return get_catalog_summary()


@router.post(
    "",
    response_model=InboundResponse,
    summary="Tiếp nhận đơn hàng Checkout từ Landing Page"
)
def receive_landing_page_order(order: LandingPageOrderIn):
    start_time = time.time()

    # 1. Chuẩn hóa danh sách sản phẩm đặt mua (Hỗ trợ cả giỏ Checkout nhiều món lẫn chọn 1 món)
    raw_items = []
    if order.items and len(order.items) > 0:
        for it in order.items:
            raw_items.append({"sku": it.sku.strip().upper(), "quantity": it.quantity})
    elif order.sku:
        raw_items.append({"sku": order.sku.strip().upper(), "quantity": order.quantity})
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vui lòng chọn ít nhất 1 sản phẩm để đặt hàng!"
        )

    # 2. Tra cứu SKU và Giá chuẩn từ Catalog của Backend (Chống giả mạo giá từ trình duyệt - P0-5)
    validated_items_map = {}
    for entry in raw_items:
        sku_code = entry["sku"]
        qty = entry["quantity"]
        product_meta = get_product_by_sku(sku_code)
        if not product_meta:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Mã sản phẩm (SKU) không tồn tại trong hệ thống: {sku_code}"
            )
        if sku_code in validated_items_map:
            validated_items_map[sku_code]["quantity"] += qty
        else:
            validated_items_map[sku_code] = {
                "sku": sku_code,
                "name": product_meta["name"],
                "product_name": product_meta["name"],
                "quantity": qty,
                "price": product_meta["price"],
                "unit_price": product_meta["price"],
            }

    validated_items = list(validated_items_map.values())
    total_amount = sum(i["price"] * i["quantity"] for i in validated_items)

    # 3. Khóa chống spam / click đúp 30 giây bằng Redis SETNX
    sku_signature = "_".join(sorted(f"{i['sku']}x{i['quantity']}" for i in validated_items))
    dedup_key = f"{order.phone}_{sku_signature}"
    is_allowed = check_and_set_dedup(dedup_key, expire_seconds=30)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn vừa gửi đơn hàng tương tự cách đây ít giây. Vui lòng đợi 30 giây trước khi đặt lại!"
        )

    # 4. Sinh mã nguồn đơn Landing Page
    source_order_id = f"LP_{uuid.uuid4().hex[:8].upper()}"
    raw_dict = {
        **order.model_dump(),
        "validated_items": validated_items,
        "validated_total_amount": total_amount,
    }

    # 5. Lưu trữ Tầng Bronze (PostgreSQL raw_orders)
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
            detail="Không thể lưu đơn hàng vào kho dữ liệu tầng Bronze."
        )

    # 6. Đóng gói và bắn message vào RabbitMQ (Exchange: orders.exchange, Key: order.landing)
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
        "items": validated_items,
        "total_amount": total_amount,
        "note": order.note,
        "ingested_at": time.time()
    }

    try:
        publish_order_event(
            routing_key=settings.ROUTING_KEY_LANDING,
            message_dict=message_payload
        )
    except Exception as e:
        print(f"[-] [LOI BAN RABBITMQ]: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đơn đã lưu kho Bronze nhưng tạm thời chưa đẩy được vào hàng đợi xử lý."
        )

    duration_ms = round((time.time() - start_time) * 1000, 2)
    items_summary = ", ".join(f"{i['sku']} x{i['quantity']}" for i in validated_items)

    print("\n" + "=" * 70)
    print(f"[GATEWAY INGESTION] TIEP NHAN THANH CONG (Thoi gian: {duration_ms} ms)")
    print(f"   * Ma don nguon:    {source_order_id}")
    print(f"   * Bronze Record:   ID #{raw_order_id} (Bang raw_orders)")
    print(f"   * Khach hang:      {order.full_name} ({order.phone})")
    print(f"   * San pham:        {items_summary} | Tong: {total_amount:,.0f} VND")
    print(f"   * RabbitMQ Queue:  orders.inbound.queue (Routing key: {settings.ROUTING_KEY_LANDING})")
    print("=" * 70 + "\n")

    return InboundResponse(
        status="success",
        message="Đơn hàng đã được lưu kho Bronze và đưa vào hàng đợi xử lý ngầm",
        source_order_id=source_order_id,
        raw_order_id=raw_order_id,
        total_amount=total_amount,
        items_count=sum(i["quantity"] for i in validated_items),
        duration_ms=duration_ms
    )

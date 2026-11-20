import logging
from hmac import compare_digest
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.core.database import get_db
from app.core.rabbitmq_client import publish_order_event
from app.schemas.order import InboundResponse
from app.schemas.shopee import ShopeeOrderNotification, ShopeeReadyOrder
from app.services.bronze_service import save_to_bronze


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shopee", tags=["Shopee Ingestion"])


@router.post("/webhook", response_model=InboundResponse, summary="Nhận chi tiết đơn Shopee đã chuẩn hóa")
def receive_shopee_order(
    payload: dict,
    token: Annotated[str | None, Header(alias="X-Shopee-Webhook-Token")] = None,
):
    start = perf_counter()
    expected_token = settings.SHOPEE_WEBHOOK_TOKEN
    if not expected_token:
        raise HTTPException(503, "Kênh Shopee chưa được cấu hình")
    if not token or not compare_digest(token.encode(), expected_token.encode()):
        raise HTTPException(401, "Token webhook Shopee không hợp lệ")

    try:
        notification = ShopeeOrderNotification.model_validate(payload)
        if notification.order_status == "READY_TO_SHIP":
            ShopeeReadyOrder.model_validate(payload)
    except ValidationError as exc:
        errors = exc.errors(include_input=False, include_context=False, include_url=False)
        raise HTTPException(422, detail=errors) from exc

    source_order_id = notification.source_order_id
    raw_order_id = None
    if notification.order_status == "READY_TO_SHIP":
        try:
            raw_order_id, queued = queue_shopee_order(source_order_id, payload)
        except Exception as exc:
            logger.exception("Không thể đưa đơn Shopee %s vào hàng đợi", source_order_id)
            raise HTTPException(503, "Chưa thể đưa đơn Shopee vào hàng đợi, vui lòng gửi lại") from exc

        result = "success" if queued else "duplicate"
        message = "Đã đưa đơn Shopee vào hàng đợi" if queued else "Đơn Shopee đã được tiếp nhận"
    else:
        result = "ignored"
        message = "Chỉ tự động chốt đơn ở trạng thái READY_TO_SHIP"

    return InboundResponse(
        status=result,
        message=message,
        source_order_id=source_order_id,
        raw_order_id=raw_order_id,
        duration_ms=round((perf_counter() - start) * 1000, 2),
    )


def queue_shopee_order(source_order_id: str, payload: dict) -> tuple[int, bool]:
    save_to_bronze("shopee", source_order_id, payload)
    with get_db() as cur:
        cur.execute(
            """
            SELECT id, process_status FROM raw_orders
            WHERE source_channel = 'shopee' AND source_order_id = %s
            FOR UPDATE;
            """,
            (source_order_id,),
        )
        row = cur.fetchone()
        if row["process_status"] != "pending":
            return row["id"], False

        # Bronze đã commit. Nếu broker chưa xác nhận, lần gửi lại có thể thử publish tiếp.
        publish_order_event(
            routing_key=settings.ROUTING_KEY_SHOPEE,
            message_dict={"source_channel": "shopee", "source_order_id": source_order_id, "raw_order_id": row["id"]},
            confirm_delivery=True,
        )
        cur.execute("UPDATE raw_orders SET process_status = 'queued' WHERE id = %s;", (row["id"],))
        return row["id"], True

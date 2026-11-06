"""
Facebook Messenger Webhook Ingestion Router
===========================================
Tiếp nhận và xác thực Webhook từ Meta Graph API:
- Task 2.1: GET  /webhook (Xác thực Meta Hub Challenge)
- Task 2.2: POST /webhook (Hứng sự kiện tin nhắn & lưu Bronze Idempotent, đẩy RabbitMQ)
"""
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.rabbitmq_client import publish_order_event
from app.services.bronze_service import save_to_bronze
from app.schemas.facebook import FacebookWebhookPayload, FacebookWebhookResponse

router = APIRouter(prefix="/facebook", tags=["Facebook Messenger Webhook"])


@router.get(
    "/webhook",
    response_class=PlainTextResponse,
    summary="Xác thực Webhook Meta (Hub Challenge - Task 2.1)"
)
def verify_facebook_webhook(
    hub_mode: str = Query(..., alias="hub.mode", description="Chế độ đăng ký, mặc định là 'subscribe'"),
    hub_verify_token: str = Query(..., alias="hub.verify_token", description="Token bí mật cài đặt trên Meta App"),
    hub_challenge: str = Query(..., alias="hub.challenge", description="Mã thử thách từ Meta")
):
    """
    Task 2.1: Xác thực Webhook Meta Graph API
    -----------------------------------------
    Meta gửi: GET /inbound/facebook/webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
    Kiểm tra verify_token khớp với cấu hình hệ thống và phản hồi chuỗi hub.challenge dạng plain text.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.FB_VERIFY_TOKEN:
        print("\n" + "=" * 70)
        print("[+] [FACEBOOK WEBHOOK] XAC THUC HUB CHALLENGE THANH CONG!")
        print(f"   * Token:     {hub_verify_token}")
        print(f"   * Challenge: {hub_challenge}")
        print("=" * 70 + "\n")
        return hub_challenge

    print("\n" + "=" * 70)
    print("[-] [FACEBOOK WEBHOOK] XAC THUC THAT BAI: Token không khớp!")
    print(f"   * Nhan duoc: {hub_verify_token}")
    print(f"   * Ky vong:   {settings.FB_VERIFY_TOKEN}")
    print("=" * 70 + "\n")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch"
    )


@router.post(
    "/webhook",
    response_model=FacebookWebhookResponse,
    summary="Tiếp nhận tin nhắn Facebook Messenger (Task 2.2)"
)
async def receive_facebook_webhook(payload: FacebookWebhookPayload):
    """
    Task 2.2: Cổng tiếp nhận sự kiện Facebook Messenger
    --------------------------------------------------
    1. Tiếp nhận payload JSON sự kiện từ Meta Graph API.
    2. Bỏ qua tin nhắn echo (tin nhắn do Fanpage gửi ra).
    3. Lưu nguyên bản JSON vào Tầng Bronze (bảng raw_orders, kiểm tra Idempotent theo source_channel + source_order_id).
    4. Bắn sự kiện sang RabbitMQ (Exchange: orders.exchange, Routing key: order.facebook.message).
    5. Phản hồi nhanh HTTP 200 cho Meta kèm trạng thái EVENT_RECEIVED.
    """
    start_time = time.time()
    processed_count = 0
    created_raw_order_ids = []

    for entry in payload.entry:
        page_id = entry.id
        events = (entry.messaging or []) + (entry.standby or [])

        for event in events:
            # 1. Bỏ qua nếu là tin nhắn do chính Fanpage gửi đi (echo)
            if event.message and event.message.is_echo:
                continue

            # 2. Bỏ qua nếu không có nội dung văn bản (chỉ xử lý tin nhắn text)
            if not event.message or not event.message.text:
                continue

            mid = event.message.mid
            sender_id = event.sender.id  # Facebook Page-Scoped ID (PSID)
            message_text = event.message.text.strip()
            source_order_id = f"FB_{mid}"

            # 3. Lưu nguyên bản Tầng Bronze kèm khóa chống trùng (Idempotent)
            try:
                raw_order_id = save_to_bronze(
                    source_channel="facebook",
                    source_order_id=source_order_id,
                    raw_payload=payload.model_dump()
                )
            except Exception as e:
                print(f"[-] [FACEBOOK INGESTION LOI BRONZE]: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Lỗi lưu trữ kho Bronze Facebook: {str(e)}"
                )

            # 3.1. Nếu raw_order_id là None -> Sự kiện Webhook bị Meta gửi lặp (Retry) -> Bỏ qua ngay (Idempotent)
            if raw_order_id is None:
                print(f"[⚡ IDEMPOTENT SKIP] Tin nhắn Facebook {source_order_id} đã được xử lý trước đó, bỏ qua!")
                continue

            created_raw_order_ids.append(raw_order_id)

            # 4. Đóng gói và bắn sự kiện vào RabbitMQ (Routing key: order.facebook.message)
            message_payload = {
                "raw_order_id": raw_order_id,
                "source_channel": "facebook",
                "source_order_id": source_order_id,
                "sender_id": sender_id,
                "page_id": page_id,
                "message_id": mid,
                "text": message_text,
                "timestamp": event.timestamp,
                "ingested_at": time.time()
            }

            try:
                publish_order_event(
                    routing_key=settings.ROUTING_KEY_FACEBOOK_MESSAGE,
                    message_dict=message_payload
                )
                processed_count += 1
            except Exception as e:
                print(f"[-] [FACEBOOK INGESTION LOI RABBITMQ]: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Lỗi đẩy vào hàng đợi RabbitMQ: {str(e)}"
                )

            duration_ms = round((time.time() - start_time) * 1000, 2)
            print("\n" + "=" * 70)
            print(f"[FACEBOOK INGESTION] TIEP NHAN TIN NHAN THANH CONG ({duration_ms} ms)")
            print(f"   * Fanpage ID:      {page_id}")
            print(f"   * Khách hàng PSID: {sender_id}")
            print(f"   * Message ID:      {mid}")
            print(f"   * Bronze Record:   ID #{raw_order_id} (Bang raw_orders)")
            print(f"   * Nội dung chat:   {message_text}")
            print(f"   * RabbitMQ Queue:  orders.inbound.queue (Routing key: {settings.ROUTING_KEY_FACEBOOK_MESSAGE})")
            print("=" * 70 + "\n")

    return FacebookWebhookResponse(
        status="EVENT_RECEIVED",
        processed_messages=processed_count,
        raw_order_ids=created_raw_order_ids
    )


@router.get('/drafts/{conversation_id}', summary='Thông tin nháp và bằng chứng để nhân viên kiểm tra')
def get_facebook_conversation_draft(conversation_id: int):
    from app.core.database import get_db
    with get_db() as cur:
        cur.execute("""SELECT d.conversation_id, d.order_id, d.state, d.updated_at
                       FROM conversation_drafts d JOIN conversations c ON c.id=d.conversation_id
                       WHERE d.conversation_id=%s AND c.channel='facebook'""", (conversation_id,))
        draft = cur.fetchone()
        if not draft:
            raise HTTPException(status_code=404, detail='Không tìm thấy bản nháp hội thoại')
        return dict(draft)

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# ==============================================================================
# 1. SCHEMA XÁC THỰC WEBHOOK META (TASK 2.1: GET /inbound/facebook/webhook)
# ==============================================================================
class FacebookWebhookVerifyQuery(BaseModel):
    hub_mode: str = Field(alias="hub.mode", description="Chế độ đăng ký của Meta (subscribe)")
    hub_verify_token: str = Field(alias="hub.verify_token", description="Token bí mật xác thực")
    hub_challenge: str = Field(alias="hub.challenge", description="Mã thử thách Meta yêu cầu phản hồi")

# ==============================================================================
# 2. SCHEMA TIẾP NHẬN SỰ KIỆN MESSENGER (TASK 2.2: POST /inbound/facebook/webhook)
# Được chuyển đổi và tinh chỉnh từ ChatbotX: integrations/messenger/src/schema.ts
# ==============================================================================
class FacebookSender(BaseModel):
    id: str = Field(..., description="Page-Scoped ID (PSID) của người gửi tin nhắn")

class FacebookRecipient(BaseModel):
    id: str = Field(..., description="ID của Fanpage nhận tin nhắn")

class FacebookMessageContent(BaseModel):
    mid: str = Field(..., description="Mã định danh tin nhắn duy nhất từ Meta (Message ID)")
    text: Optional[str] = Field(None, description="Nội dung văn bản tin nhắn của khách")
    is_echo: Optional[bool] = Field(False, description="True nếu tin nhắn do Fanpage gửi đi (echo)")
    quick_reply: Optional[Dict[str, Any]] = Field(None, description="Dữ liệu phản hồi nhanh nếu có")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="Danh sách tệp đính kèm/ảnh")

class FacebookMessagingEvent(BaseModel):
    sender: FacebookSender
    recipient: FacebookRecipient
    timestamp: int
    message: Optional[FacebookMessageContent] = None

class FacebookEntry(BaseModel):
    id: str = Field(..., description="Fanpage ID")
    time: int = Field(..., description="Thời gian phát sinh sự kiện")
    messaging: Optional[List[FacebookMessagingEvent]] = Field(default_factory=list, description="Danh sách sự kiện hội thoại")
    standby: Optional[List[FacebookMessagingEvent]] = Field(default_factory=list, description="Danh sách sự kiện chế độ chờ (standby)")

class FacebookWebhookPayload(BaseModel):
    object: str = Field(..., description="Thường là 'page'")
    entry: List[FacebookEntry] = Field(default_factory=list, description="Danh sách entry gửi từ Meta")

class FacebookWebhookResponse(BaseModel):
    status: str = Field(default="EVENT_RECEIVED", description="Trạng thái phản hồi Meta")
    processed_messages: int = Field(default=0, description="Số lượng tin nhắn đã đưa vào hàng đợi")
    raw_order_ids: List[int] = Field(default_factory=list, description="Danh sách Bronze ID đã tạo")


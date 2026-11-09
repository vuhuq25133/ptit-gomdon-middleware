from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from app.services.chat_extractor import extract_phone


class CheckoutItemIn(BaseModel):
    sku: str = Field(..., min_length=3, description="Mã SKU chuẩn của sản phẩm")
    quantity: int = Field(default=1, ge=1, le=50, description="Số lượng đặt mua (1 - 50)")


class LandingPageOrderIn(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=120, description="Họ và tên người nhận")
    phone: str = Field(..., min_length=9, max_length=20, description="Số điện thoại người nhận")
    address: str = Field(..., min_length=5, max_length=300, description="Địa chỉ giao hàng chi tiết")
    city: str = Field(..., min_length=2, max_length=100, description="Tỉnh / Thành phố")
    # Hỗ trợ cả đặt 1 món truyền thống (sku + quantity) hoặc giỏ Checkout nhiều món (items)
    sku: Optional[str] = Field(None, description="Mã sản phẩm đặt mua (nếu đặt 1 món)")
    quantity: int = Field(default=1, ge=1, le=50, description="Số lượng (nếu đặt 1 món)")
    unit_price: Optional[float] = Field(default=None, description="Đơn giá (Backend sẽ tự tra lại theo Catalog chuẩn)")
    items: Optional[List[CheckoutItemIn]] = Field(default=None, description="Danh sách sản phẩm trong giỏ Checkout")
    note: Optional[str] = Field(None, max_length=500, description="Ghi chú đơn hàng")

    @field_validator("full_name", "address", "city")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Trường thông tin không được để trống")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_vn_phone(cls, v: str) -> str:
        normalized = extract_phone(v)
        if not normalized:
            raise ValueError("Số điện thoại không hợp lệ (cần 10 số di động Việt Nam: 03x, 05x, 07x, 08x, 09x)")
        return normalized


class InboundResponse(BaseModel):
    status: str
    message: str
    source_order_id: str
    raw_order_id: Optional[int] = None
    total_amount: Optional[float] = None
    items_count: Optional[int] = None
    duration_ms: float

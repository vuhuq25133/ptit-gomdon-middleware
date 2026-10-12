from pydantic import BaseModel, Field
from typing import Optional, List

class LandingPageOrderIn(BaseModel):
    full_name: str = Field(..., description="Họ và tên người nhận")
    phone: str = Field(..., description="Số điện thoại người nhận")
    address: str = Field(..., description="Địa chỉ giao hàng chi tiết")
    city: str = Field(..., description="Tỉnh / Thành phố")
    sku: str = Field(..., description="Mã sản phẩm đặt mua")
    quantity: int = Field(default=1, ge=1, description="Số lượng")
    unit_price: float = Field(default=250000.0, description="Đơn giá")
    note: Optional[str] = Field(None, description="Ghi chú đơn hàng")

class InboundResponse(BaseModel):
    status: str
    message: str
    source_order_id: str
    raw_order_id: Optional[int] = None
    duration_ms: float

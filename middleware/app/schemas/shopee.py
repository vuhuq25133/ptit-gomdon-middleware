from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.services.chat_extractor import extract_phone


Sku = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Money = Annotated[float, Field(ge=0, le=9_999_999_999.99, allow_inf_nan=False)]


class ShopeeOrderNotification(BaseModel):
    shop_id: int = Field(gt=0, le=9_223_372_036_854_775_807)
    order_sn: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    order_status: str = Field(min_length=1, max_length=32)

    @property
    def source_order_id(self) -> str:
        return f"{self.shop_id}:{self.order_sn}"


class ShopeeBuyer(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    phone: str

    @model_validator(mode="after")
    def validate_phone(self):
        phone = extract_phone(self.phone)
        if phone is None:
            raise ValueError("Thiếu số điện thoại giao hàng hợp lệ")
        self.phone = phone
        return self


class ShopeeAddress(BaseModel):
    full_address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ShopeeOrderItem(BaseModel):
    item_name: str | None = Field(default=None, max_length=255)
    item_sku: Sku = ""
    model_sku: Sku = ""
    model_quantity_purchased: int = Field(gt=0, le=2_147_483_647)
    model_discounted_price: Money

    @property
    def source_sku(self) -> str:
        return self.model_sku or self.item_sku

    @model_validator(mode="after")
    def validate_sku(self):
        if not self.source_sku:
            raise ValueError("Dòng sản phẩm thiếu SKU Shopee")
        return self


class ShopeeReadyOrder(ShopeeOrderNotification):
    buyer_user: ShopeeBuyer
    recipient_address: ShopeeAddress
    item_list: list[ShopeeOrderItem] = Field(min_length=1)
    total_amount: Money
    note: str | None = None

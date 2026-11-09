import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from datetime import datetime

mock_app = FastAPI(
    title="ShopTrack Partner Mock API Server",
    description="Hệ thống Mock giả lập API của đối tác ShopTrack.vn cho đồ án tốt nghiệp PTIT",
    version="1.0.0"
)

# Lưu trữ bộ nhớ tạm mô phỏng DB của ShopTrack
DB_ORDERS = {}
SEEN_IDEMPOTENCY_KEYS = {}

class OrderItem(BaseModel):
    sku: str
    quantity: int
    price: float

class CreateOrderPayload(BaseModel):
    source_channel: str
    source_order_id: str
    customer_name: str
    customer_phone: str
    shipping_address: str
    shipping_city: str
    note: Optional[str] = None
    items: List[OrderItem]
    total_amount: float

@mock_app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "ShopTrack Partner Mock",
        "timestamp": datetime.now().isoformat()
    }

@mock_app.post("/api/v1/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    payload: CreateOrderPayload, 
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
):
    # 1. Kiểm tra chống đẩy trùng đơn (Idempotency): Trả về đúng mã đơn cũ nếu gọi lại
    if idempotency_key:
        if idempotency_key in SEEN_IDEMPOTENCY_KEYS:
            cached = SEEN_IDEMPOTENCY_KEYS[idempotency_key]
            return {
                "status": "duplicate_prevented",
                "message": "Đơn hàng đã được ghi nhận trước đó với khóa Idempotency này",
                "order_id": cached["order_id"],
                "tracking_code": cached["tracking_code"],
                "created_at": cached["created_at"]
            }

    # 2. Tạo đơn mới trên ShopTrack
    shoptrack_order_id = f"ST_{len(DB_ORDERS) + 1:05d}"
    tracking_code = f"VNPOST_{shoptrack_order_id}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "shoptrack_order_id": shoptrack_order_id,
        "tracking_code": tracking_code,
        "received_at": now_str,
        "payload": payload.model_dump()
    }
    DB_ORDERS[shoptrack_order_id] = record

    response_data = {
        "status": "success",
        "order_id": shoptrack_order_id,
        "tracking_code": tracking_code,
        "created_at": now_str
    }
    if idempotency_key:
        SEEN_IDEMPOTENCY_KEYS[idempotency_key] = response_data

    items_summary = (
        ", ".join(f"{it.sku} (x{it.quantity})" for it in payload.items)
        if payload.items
        else "Không có sản phẩm"
    )

    print("\n" + "="*70)
    print(f"[SHOPTRACK MOCK] NHAN DON HANG MOI THANH CONG")
    print(f"   * Ma don ShopTrack: {shoptrack_order_id} | Van don: {tracking_code}")
    print(f"   * Kenh ban hang:    {payload.source_channel.upper()} ({payload.source_order_id})")
    print(f"   * Khach hang:       {payload.customer_name} - SDT: {payload.customer_phone}")
    print(f"   * Dia chi giao:     {payload.shipping_address}, {payload.shipping_city}")
    print(f"   * San pham (SKU):   {items_summary}")
    print(f"   * Tong tien COD:    {payload.total_amount:,.0f} VND")
    print("="*70 + "\n")

    return response_data

@mock_app.get("/api/v1/orders")
def list_orders():
    return {
        "total_orders": len(DB_ORDERS),
        "orders": list(DB_ORDERS.values())
    }

if __name__ == "__main__":
    print("[*] Dang khoi dong ShopTrack Mock Server tai cong 8001...")
    uvicorn.run(mock_app, host="127.0.0.1", port=8001)

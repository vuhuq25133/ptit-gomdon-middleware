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
from threading import Lock

mock_app = FastAPI(
    title="ShopTrack Partner Mock API Server",
    description="Hệ thống Mock giả lập API của đối tác ShopTrack.vn cho đồ án tốt nghiệp PTIT",
    version="1.0.0"
)

# Lưu trữ bộ nhớ tạm mô phỏng DB của ShopTrack
DB_ORDERS = {}
IDEMPOTENCY_ORDERS = {}
ORDERS_LOCK = Lock()

class OrderItem(BaseModel):
    sku: str
    quantity: int
    price: float

class CreateOrderPayload(BaseModel):
    source_channel: str
    source_order_id: str
    source_metadata: dict | None = None
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
    with ORDERS_LOCK:
        existing_id = IDEMPOTENCY_ORDERS.get(idempotency_key)
        if existing_id is not None:
            return {
                "status": "duplicate_prevented",
                "message": "Đơn hàng đã được ghi nhận trước đó với khóa Idempotency này",
                "order_id": existing_id,
                "tracking_code": f"VNPOST_{existing_id}",
                "created_at": DB_ORDERS[existing_id]["received_at"],
            }

        shoptrack_order_id = f"ST_{len(DB_ORDERS) + 1:05d}"
        order_payload = payload.model_dump()
        if payload.source_metadata is None:
            order_payload.pop("source_metadata")
        record = {
            "shoptrack_order_id": shoptrack_order_id,
            "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payload": order_payload,
        }
        DB_ORDERS[shoptrack_order_id] = record
        if idempotency_key:
            IDEMPOTENCY_ORDERS[idempotency_key] = shoptrack_order_id

    print("\n" + "="*70)
    print(f"[SHOPTRACK MOCK] NHAN DON HANG MOI THANH CONG")
    print(f"   * Ma don ShopTrack: {shoptrack_order_id}")
    print(f"   * Kenh ban hang:    {payload.source_channel.upper()}")
    print(f"   * Khach hang:       {payload.customer_name} - SDT: {payload.customer_phone}")
    print(f"   * Dia chi giao:     {payload.shipping_address}, {payload.shipping_city}")
    print(f"   * San pham (SKU):   {payload.items[0].sku} (So luong: {payload.items[0].quantity})")
    print(f"   * Tong tien COD:    {payload.total_amount:,.0f} VND")
    print("="*70 + "\n")

    return {
        "status": "success",
        "order_id": shoptrack_order_id,
        "tracking_code": f"VNPOST_{shoptrack_order_id}",
        "created_at": record["received_at"]
    }

@mock_app.get("/api/v1/orders")
def list_orders():
    with ORDERS_LOCK:
        return {"total_orders": len(DB_ORDERS), "orders": list(DB_ORDERS.values())}

if __name__ == "__main__":
    print("[*] Dang khoi dong ShopTrack Mock Server tai cong 8001...")
    uvicorn.run(mock_app, host="127.0.0.1", port=8001)

from app.core.database import get_db
from app.schemas.shopee import ShopeeReadyOrder
from app.services.bronze_service import update_bronze_status
from app.services.shoptrack_service import push_order_to_shoptrack
from app.services.silver_service import create_silver_order, get_or_create_customer


def handle_shopee_order(data: dict):
    raw_order_id = data["raw_order_id"]
    with get_db() as cur:
        cur.execute(
            """
            SELECT raw.source_order_id, raw.raw_payload, orders.order_code
            FROM raw_orders AS raw
            LEFT JOIN orders USING (source_channel, source_order_id)
            WHERE raw.id = %s AND raw.source_channel = 'shopee';
            """,
            (raw_order_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Không tìm thấy đơn Shopee Bronze #{raw_order_id}")

    order = ShopeeReadyOrder.model_validate(row["raw_payload"])
    if order.order_status != "READY_TO_SHIP" or order.source_order_id != row["source_order_id"]:
        raise ValueError(f"Đơn Shopee Bronze #{raw_order_id} không hợp lệ để chốt")

    order_code = row["order_code"] or create_shopee_silver_order(raw_order_id, order)
    push_order_to_shoptrack(order_code, source_metadata={"shop_id": order.shop_id, "order_sn": order.order_sn})
    update_bronze_status(raw_order_id, "processed")


def create_shopee_silver_order(raw_order_id: int, order: ShopeeReadyOrder) -> str:
    source_skus = sorted({item.source_sku for item in order.item_list})
    with get_db() as cur:
        cur.execute(
            "SELECT source_sku, standard_sku FROM sku_mappings WHERE source_channel = 'shopee' AND source_sku = ANY(%s);",
            (source_skus,),
        )
        sku_mappings = {row["source_sku"]: row["standard_sku"].strip() for row in cur.fetchall()}

    missing = [sku for sku in source_skus if not 1 <= len(sku_mappings.get(sku, "")) <= 50]
    if missing:
        raise ValueError(f"SKU Shopee chưa có mã kho hợp lệ: {', '.join(missing)}")

    buyer = order.buyer_user
    address = order.recipient_address
    customer_id = get_or_create_customer(buyer.phone, buyer.name, address.full_address, address.city)
    items = [
        {
            "sku": sku_mappings[item.source_sku],
            "name": item.item_name or sku_mappings[item.source_sku],
            "quantity": item.model_quantity_purchased,
            "price": item.model_discounted_price,
        }
        for item in order.item_list
    ]
    return create_silver_order(
        raw_order_id=raw_order_id,
        source_channel="shopee",
        source_order_id=order.source_order_id,
        customer_id=customer_id,
        shipping_name=buyer.name,
        shipping_phone=buyer.phone,
        shipping_address=address.full_address,
        shipping_city=address.city,
        items=items,
        total_amount=order.total_amount,
        status="processing",
        note=order.note,
    )

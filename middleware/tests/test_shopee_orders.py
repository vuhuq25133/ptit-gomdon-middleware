import json
import unittest
from pathlib import Path
from unittest.mock import call, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.inbound import router
from app.core.config import settings
from app.schemas.shopee import ShopeeReadyOrder
from app.services import shoptrack_service
from app.workers.handlers import shopee_handler
import mock_shoptrack


class ShopeeOrderTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).parent / "mock_data" / "shopee_order_webhook.json"
        self.payload = json.loads(fixture.read_text(encoding="utf-8"))
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.path = "/inbound/shopee/webhook"
        self.headers = {"X-Shopee-Webhook-Token": "test-token"}
        token_patch = patch.object(settings, "SHOPEE_WEBHOOK_TOKEN", "test-token")
        token_patch.start()
        self.addCleanup(token_patch.stop)

    @patch("app.api.shopee.queue_shopee_order")
    def test_only_ready_valid_orders_are_queued(self, queue):
        self.assertEqual(self.client.post(self.path, json=self.payload).status_code, 401)
        cancelled = {"shop_id": self.payload["shop_id"], "order_sn": self.payload["order_sn"], "order_status": "CANCELLED"}
        self.assertEqual(self.client.post(self.path, headers=self.headers, json=cancelled).json()["status"], "ignored")
        incomplete = {**cancelled, "order_status": "READY_TO_SHIP"}
        self.assertEqual(self.client.post(self.path, headers=self.headers, json=incomplete).status_code, 422)
        queue.assert_not_called()

        queue.side_effect = [(12, True), (12, False)]
        accepted = self.client.post(self.path, headers=self.headers, json=self.payload).json()
        duplicate = self.client.post(self.path, headers=self.headers, json=self.payload).json()
        self.assertEqual((accepted["status"], duplicate["status"]), ("success", "duplicate"))
        self.assertEqual(accepted["raw_order_id"], 12)
        self.assertEqual(queue.call_args_list, [call("998811:241006ABC9988XYZ", self.payload)] * 2)

    @patch.object(shopee_handler, "get_db")
    @patch.object(shopee_handler, "get_or_create_customer", return_value=7)
    @patch.object(shopee_handler, "create_silver_order")
    def test_priority_of_variant_sku_and_missing_mapping(self, create_order, create_customer, get_db):
        self.payload["item_list"][0]["model_sku"] = "SHOPEE-VARIANT-L"
        order = ShopeeReadyOrder.model_validate(self.payload)
        cursor = get_db.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        with self.assertRaisesRegex(ValueError, "SHOPEE-VARIANT-L"):
            shopee_handler.create_shopee_silver_order(12, order)
        create_customer.assert_not_called()
        create_order.assert_not_called()

        cursor.fetchall.return_value = [{"source_sku": "SHOPEE-VARIANT-L", "standard_sku": "POLO-BLK-L"}]
        shopee_handler.create_shopee_silver_order(12, order)
        self.assertEqual(create_order.call_args.kwargs["status"], "processing")
        self.assertEqual(create_order.call_args.kwargs["items"][0]["sku"], "POLO-BLK-L")

    @patch.object(shoptrack_service, "get_db")
    @patch.object(shoptrack_service.httpx, "post")
    def test_retry_after_lost_shoptrack_reply_uses_same_partner_order(self, post, get_db):
        cursor = get_db.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            "id": 88, "source_channel": "shopee", "source_order_id": "test:lost-reply",
            "shipping_name": "Người nhận", "shipping_phone": "0977665544", "shipping_address": "Văn Quán",
            "shipping_city": "Hà Nội", "note": None, "status": "processing", "shoptrack_order_id": None,
            "total_amount": 239000,
        }
        cursor.fetchall.return_value = [{"sku": "POLO-BLK-L", "price": 239000, "quantity": 1}]
        with patch.multiple(mock_shoptrack, DB_ORDERS={}, IDEMPOTENCY_ORDERS={}), TestClient(mock_shoptrack.mock_app) as partner:
            original_ids = []

            def forward(_url, *, json, headers, timeout):
                response = partner.post("/api/v1/orders", json=json, headers=headers)
                if not original_ids:
                    original_ids.append(response.json()["order_id"])
                    raise httpx.ReadTimeout("Mất phản hồi khi ShopTrack đã nhận đơn")
                return response

            post.side_effect = forward
            metadata = {"shop_id": 998811, "order_sn": "lost-reply"}
            with self.assertRaisesRegex(RuntimeError, "Không thể đồng bộ"):
                shoptrack_service.push_order_to_shoptrack("ORD_TEST", metadata)
            self.assertEqual(cursor.execute.call_args.args[1][-1], "failed")
            shoptrack_service.push_order_to_shoptrack("ORD_TEST", metadata)
            self.assertEqual(cursor.execute.call_args.args[1][0], original_ids[0])
            self.assertEqual(partner.get("/api/v1/orders").json()["total_orders"], 1)

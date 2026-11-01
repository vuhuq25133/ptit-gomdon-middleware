"""
Inbound Ingestion Gateway (Router Aggregator)
=============================================
Tập hợp các luồng tiếp nhận đơn hàng đa kênh:
- Landing Page:   /inbound/landing-page (REST API)
- Facebook:       /inbound/facebook/webhook (Meta Graph API Webhook)
"""
from fastapi import APIRouter

from app.api.landing_page import router as landing_page_router
from app.api.facebook import router as facebook_router

# Router tổng /inbound
router = APIRouter(prefix="/inbound")

# 1. Tích hợp kênh Landing Page
router.include_router(landing_page_router)

# 2. Tích hợp kênh Facebook Messenger
router.include_router(facebook_router)

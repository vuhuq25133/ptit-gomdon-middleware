-- ====================================================================
-- HỆ THỐNG GOM ĐƠN ĐA NỀN TẢNG (ORDER CONSOLIDATION MIDDLEWARE)
-- ĐỒ ÁN TỐT NGHIỆP PTIT - KIẾN TRÚC LAKEHOUSE & EVENT-DRIVEN
-- Database: gomdon_lakehouse
-- ====================================================================

-- 1. TẦNG BRONZE: KHO HỨNG THÔ (RAW LAKEHOUSE INGESTION)
-- Lưu trữ nguyên si JSON payload của mọi kênh (Landing Page, FB, Zalo, Shopee...)
-- Quy tắc Idempotency: UNIQUE (source_channel, source_order_id) chống trùng lặp sự kiện Webhook
CREATE TABLE IF NOT EXISTS raw_orders (
    id BIGSERIAL PRIMARY KEY,
    source_channel VARCHAR(50) NOT NULL,            -- landing_page, facebook_comment, facebook_message, zalo, shopee...
    source_order_id VARCHAR(100),                   -- ID từ kênh gốc nếu có
    raw_payload JSONB NOT NULL,                     -- JSON nguyên bản không qua chỉnh sửa
    process_status VARCHAR(30) DEFAULT 'pending',   -- pending, processed, failed
    error_message TEXT,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_raw_orders_channel_source_id UNIQUE (source_channel, source_order_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_orders_channel ON raw_orders(source_channel);
CREATE INDEX IF NOT EXISTS idx_raw_orders_status ON raw_orders(process_status);

-- 2. TẦNG SILVER: HỒ SƠ KHÁCH HÀNG (DEDUP THEO SỐ ĐIỆN THOẠI)
-- Quy tắc: "Một khách hàng - Một hồ sơ duy nhất"
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,              -- Khóa chính định danh tự nhiên
    full_name VARCHAR(150),
    shipping_address TEXT,
    shipping_city VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Định danh đa kênh: Map nick Facebook (PSID) / Zalo (User ID) về cùng 1 customer_id
CREATE TABLE IF NOT EXISTS customer_identities (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL,                   -- facebook, zalo, shopee...
    identity_value VARCHAR(100) NOT NULL,           -- PSID hoặc Zalo User ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (channel, identity_value)
);

-- 3. TẦNG SILVER: ĐƠN HÀNG CHUẨN HÓA (CANONICAL SCHEMA)
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_code VARCHAR(50) UNIQUE NOT NULL,         -- Mã nội bộ chuẩn: ORD_YYYYMMDD_XXXX
    source_channel VARCHAR(50) NOT NULL,            -- landing_page, facebook, zalo, shopee
    source_order_id VARCHAR(100),                   -- Mã đơn gốc từ kênh
    customer_id INT REFERENCES customers(id),
    shipping_name VARCHAR(150) NOT NULL,
    shipping_phone VARCHAR(20) NOT NULL,
    shipping_address TEXT NOT NULL,
    shipping_city VARCHAR(100) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) DEFAULT 'draft',             -- draft, processing, pushed_to_shoptrack, failed
    shoptrack_order_id VARCHAR(50),                 -- Mã xuất kho ST_... từ ShopTrack
    tracking_code VARCHAR(50),                      -- Mã vận đơn bưu cục VNPOST_...
    raw_order_id BIGINT REFERENCES raw_orders(id),  -- Liên kết ngược vết về Tầng Bronze
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_orders_channel_source_id UNIQUE (source_channel, source_order_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);

-- Chi tiết từng dòng sản phẩm trong đơn hàng
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
    sku VARCHAR(50) NOT NULL,                       -- Mã SKU sản phẩm chuẩn
    product_name VARCHAR(255),
    quantity INT NOT NULL CHECK (quantity > 0),
    price NUMERIC(12, 2) NOT NULL
);

-- 4. HỘP THƯ CHUNG ĐA KÊNH (DÀNH CHO GIAI ĐOẠN 2 & 3: FACEBOOK / ZALO)
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    channel VARCHAR(50) NOT NULL,                   -- facebook, zalo
    channel_conversation_id VARCHAR(100) NOT NULL,
    customer_id INT REFERENCES customers(id),
    sender_name VARCHAR(255),                       -- Nickname Facebook / Zalo (lấy từ Graph API)
    sender_avatar TEXT,                             -- URL avatar người nhắn
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS sender_name VARCHAR(255);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS sender_avatar TEXT;

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
    sender_type VARCHAR(20) NOT NULL,               -- customer, shop
    content TEXT,
    has_extracted_order BOOLEAN DEFAULT FALSE,      -- Đã trích xuất thành đơn nháp chưa
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. CẤU HÌNH HỆ THỐNG & NHẬT KÝ ĐỒNG BỘ (AUDIT LOGS)
-- Ánh xạ mã sản phẩm đa sàn (Shopee/TikTok SKU -> Chuẩn ShopTrack)
CREATE TABLE IF NOT EXISTS sku_mappings (
    id SERIAL PRIMARY KEY,
    source_channel VARCHAR(50) NOT NULL,
    source_sku VARCHAR(100) NOT NULL,
    standard_sku VARCHAR(100) NOT NULL,
    UNIQUE (source_channel, source_sku)
);

-- Lưu App ID, App Secret, Access Token của Fanpage / Zalo OA
CREATE TABLE IF NOT EXISTS channel_configs (
    id SERIAL PRIMARY KEY,
    channel VARCHAR(50) UNIQUE NOT NULL,
    app_id VARCHAR(100),
    app_secret VARCHAR(255),
    access_token TEXT,
    webhook_verify_token VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Ghi log lịch sử đẩy đơn sang ShopTrack phục vụ đối soát & retry
CREATE TABLE IF NOT EXISTS sync_audit_logs (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id),
    action VARCHAR(50) NOT NULL,                    -- push_to_shoptrack, webhook_inbound...
    request_payload JSONB,
    response_payload JSONB,
    http_status INT,
    status VARCHAR(30) NOT NULL,                    -- success, failed, retried
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Persistent anonymous chat drafts; safe to apply to an existing installation.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS raw_order_id BIGINT REFERENCES raw_orders(id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_raw_order ON messages(raw_order_id);
CREATE TABLE IF NOT EXISTS conversation_drafts (
    conversation_id INT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    order_id INT REFERENCES orders(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

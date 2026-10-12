---
name: order-consolidation
description: >-
  Hướng dẫn quy chuẩn thiết kế, chuẩn hóa và xử lý pipeline gom đơn đa kênh
  (Landing Page, Facebook, Zalo, Shopee, TikTok) tích hợp phần mềm Shoptrack.
---

# Quy trình Pipeline Gom đơn Đa nền tảng (Order Consolidation Pipeline)

## 1. PIPELINE 4 BƯỚC BẮT BUỘC

Mọi dữ liệu đơn hàng và hội thoại từ 5 kênh đầu vào đều phải đi qua 4 bước chuẩn hóa:

```
[1. Thu thập (Ingest)] ──→ [2. Chuẩn hóa (Normalize)] ──→ [3. Khử trùng (Dedup)] ──→ [4. Đẩy đi (Push)]
```

### Bước 1: Thu thập (Ingestion)
- Hứng Webhook hoặc nhận Request từ Form/Sàn.
- Xác thực chữ ký số (Webhook Signature Verification) từ Meta / Zalo.
- Phản hồi HTTP 200 OK ngay lập tức (<100ms) để tránh nền tảng retry spam.
- Đẩy gói tin thô (Raw Payload) vào hàng đợi **RabbitMQ / Redis Streams**.

### Bước 2: Chuẩn hóa (Normalization)
Worker lấy dữ liệu từ hàng đợi và chuyển đổi về **Unified Schema**:
- **Khách hàng**: `full_name`, `phone`, `address`, `channel_user_id`.
- **Đơn hàng**: `source_channel`, `source_order_id`, `items` (SKU, số lượng, đơn giá), `total_amount`, `notes`.
- **Metadata nguồn**: `page_id`, `post_id` (nếu comment), `campaign_id` (nếu landing page).

### Bước 3: Kiểm tra & Khử trùng (Validate & Deduplication)
- **Quy tắc 1 (Một khách, một hồ sơ)**: Tra cứu bảng `customers` theo `phone`. Nếu đã có, tái sử dụng `customer_id`, không tạo bản ghi khách hàng mới.
- **Quy tắc 2 (Một sản phẩm, một mã SKU)**: Tra cứu bảng `sku_mappings` để chuyển đổi SKU sàn sang `master_sku` của Shoptrack.
- **Quy tắc 3 (Phân luồng trạng thái đơn)**:
  - Đơn từ **Landing Page, Shopee, TikTok**: Đủ thông tin $\rightarrow$ Đẩy thẳng tự động (`status = 'approved'`).
  - Đơn từ **Facebook, Zalo**: Dữ liệu từ văn bản tự do $\rightarrow$ Dừng ở bước này dưới dạng **Đơn nháp (`status = 'draft'`)**. Chờ nhân viên xác nhận mới chuyển sang bước 4.

### Bước 4: Đẩy sang Shoptrack (Push to Shoptrack)
- Gọi REST API sang Shoptrack: `POST /api/v1/orders` kèm `X-Idempotency-Key = hash(source_channel + source_order_id)`.
- Nhận mã đơn `shoptrack_order_id` lưu lại vào hệ thống.
- **Quy tắc 4 (Lỗi thì giữ lại và thử lại)**: Nếu Shoptrack lỗi mạng/5xx $\rightarrow$ Đẩy vào Retry Queue (với exponential backoff), sau 5 lần thất bại chuyển sang Dead Letter Queue (DLQ) và bắn thông báo.

---

## 2. QUY CHUẨN XỬ LÝ TEXT CHAT TIẾNG VIỆT (NER & REGEX)

Khi xử lý tin nhắn/comment từ Facebook và Zalo:
1. **Bóc tách Số điện thoại**:
   - Nhận diện các định dạng: `09xxxxxxxx`, `+84xxxxxxxxx`, `09xx.xxx.xxx`, `09xx xxx xxx`.
   - Chuẩn hóa về dạng duy nhất 10 số bắt đầu bằng `0`.
2. **Ẩn Comment tự động trên Facebook**:
   - Nếu comment bài viết hoặc livestream có chứa SĐT $\rightarrow$ Gọi ngay Facebook Graph API ẩn comment (`is_hidden = true`) để bảo vệ thông tin khách hàng và chống bị đối thủ cướp khách.

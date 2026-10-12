---
name: webhook-integrator
description: >-
  Quy chuẩn tích hợp, kiểm thử và debug Webhook thời gian thực cho Facebook Graph API,
  Zalo OA API và kết nối ngược 2 chiều với Shoptrack.
---

# Quy trình Tích hợp Webhook Đa kênh (Webhook Integrator)

## 1. THIẾT LẬP MÔI TRƯỜNG PHÁT TRIỂN & TEST CỤC BỘ

Vì Meta (Facebook) và Zalo yêu cầu URL Webhook phải là **HTTPS công khai có chứng chỉ SSL hợp lệ**, quy trình test từ máy local như sau:

1. Chạy FastAPI backend tại cổng nội bộ: `uvicorn app.main:app --port 8000 --reload`
2. Mở cổng qua Tunnel công khai:
   ```bash
   ngrok http 8000
   ```
3. Lấy URL được cấp (ví dụ: `https://abcd-1234.ngrok-free.app`) để cấu hình vào portal Meta / Zalo Developer.

---

## 2. QUY CHUẨN XÁC THỰC WEBHOOK (VERIFICATION)

### A. Facebook Webhook (Meta for Developers)
- **Endpoint GET (Xác thực đăng ký)**:
  - Meta gửi request: `GET /api/v1/webhook/facebook?hub.mode=subscribe&hub.challenge=1158201444&hub.verify_token=MY_SECRET_TOKEN`
  - Backend phải kiểm tra: Nếu `hub.verify_token == MY_SECRET_TOKEN` thì trả về giá trị `hub.challenge` dưới dạng plain text và mã HTTP 200.
- **Endpoint POST (Nhận dữ liệu sự kiện)**:
  - Bắt buộc kiểm tra chữ ký `X-Hub-Signature-256` bằng mã băm HMAC-SHA256 của payload thô với `APP_SECRET`.
  - Nếu hợp lệ $\rightarrow$ Trả về `{"status": "ok"}` (200 OK) ngay lập tức, sau đó đẩy sự kiện vào hàng đợi xử lý.

### B. Zalo OA Webhook
- Zalo gửi dữ liệu sự kiện qua `POST /api/v1/webhook/zalo`.
- Kiểm tra header chữ ký số để đảm bảo gói tin do máy chủ Zalo gửi đến.
- Xử lý các sự kiện chính:
  - `user_send_text`: Khách nhắn tin văn bản $\rightarrow$ Bóc tách SĐT/Địa chỉ $\rightarrow$ Tạo đơn nháp.
  - `user_send_image`: Khách gửi ảnh bill chuyển khoản $\rightarrow$ Tải ảnh, lưu URL đính kèm vào đơn.

---

## 3. TƯƠNG TÁC 2 CHIỀU (OUTBOUND MESSAGING)

Để nhân viên CSKH trả lời từ Shoptrack và tin nhắn tự bay về Messenger/Zalo của khách:
1. Shoptrack gửi yêu cầu sang Middleware:
   `POST /api/v1/outbound/messages`
   ```json
   {
     "channel": "facebook",
     "page_id": "10023456789",
     "recipient_id": "9876543210",
     "message_text": "Chào bạn, đơn hàng của bạn đã được xác nhận nhé!"
   }
   ```
2. Middleware tra cứu `page_access_token` tương ứng với `page_id` trong cơ sở dữ liệu.
3. Middleware gọi Graph API của Meta:
   `POST https://graph.facebook.com/v19.0/{page_id}/messages`
4. Trả về kết quả xác nhận cho Shoptrack.

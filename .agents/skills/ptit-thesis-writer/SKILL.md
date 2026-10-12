---
name: ptit-thesis-writer
description: >-
  Hướng dẫn quy chuẩn cấu trúc, văn phong học thuật và các tiêu chí phản biện
  đối với cuốn Báo cáo Đồ án Tốt nghiệp (60-100 trang) tại Học viện PTIT.
---

# Quy chuẩn Soạn thảo Báo cáo ĐATN PTIT (Thesis Writing Guidelines)

## 1. CẤU TRÚC 5 CHƯƠNG CHUẨN ĐỒ ÁN PTIT

Cuốn khóa luận tốt nghiệp ngành CNTT / KTPM / KTDL tại PTIT bắt buộc tuân theo bố cục 5 chương:

### Chương 1: Tổng quan bài toán và Khảo sát hiện trạng (15 – 20 trang)
- Bối cảnh thương mại điện tử đa kênh tại Việt Nam (Bán hàng đồng thời trên Web, Fanpage, Zalo, Sàn Shopee, TikTok Shop).
- Nêu rõ vấn đề thực tế (Pain Points): Nhập liệu thủ công phân tán, sai sót thông tin giao hàng, trùng lặp hồ sơ khách hàng.
- Khảo sát các giải pháp hiện nay (Pancake, Nhanh.vn, Haravan, Zapier) và chỉ ra điểm giới hạn.
- Mục tiêu và phạm vi cụ thể của đồ án (Hệ thống gom đơn tích hợp Shoptrack).

### Chương 2: Cơ sở lý thuyết và Công nghệ liên quan (20 – 25 trang)
- Kiến trúc hướng sự kiện (Event-driven Architecture) và Webhook thời gian thực.
- Hàng đợi thông điệp (Message Broker: RabbitMQ, Celery) và cơ chế Dead Letter Queue.
- Kỹ thuật bóc tách thực thể tiếng Việt (Regex, NLP / Named Entity Recognition).
- Kỹ thuật khử trùng lặp (Entity Resolution / Customer Deduplication) và tính toán Idempotent API.
- Tổng quan về RESTful API và cơ chế bảo mật xác thực OAuth2 / Webhook Signature.

### Chương 3: Phân tích và Thiết kế hệ thống (25 – 35 trang)
- Yêu cầu chức năng và phi chức năng (Độ trễ <100ms cho webhook, không mất dữ liệu đơn hàng).
- Biểu đồ Use Case tổng thể và chi tiết từng tác nhân.
- Biểu đồ tuần tự (Sequence Diagram) cho 5 luồng: Landing Page, Facebook (Comment/Messenger), Zalo OA, Shopee, TikTok.
- Thiết kế cơ sở dữ liệu: Mô hình quan hệ thực thể (ERD) với 6 bảng cốt lõi và 3 bảng hỗ trợ.
- Thiết kế kiến trúc module (Clean Architecture / Adapter Pattern).

### Chương 4: Triển khai thực nghiệm và Đánh giá kết quả (15 – 20 trang)
- Môi trường triển khai (FastAPI, PostgreSQL, Redis, RabbitMQ, Docker).
- Đánh giá thực nghiệm độ chính xác bóc tách thông tin (Precision, Recall, F1-Score trên tập mẫu tiếng Việt).
- Đánh giá hiệu năng chịu tải (Load Testing với Locust: Throughput, Latency khi nhận đồng thời 1.000 webhook/phút).
- Demo kết quả tích hợp 5 kênh với Shoptrack và chức năng hộp thư chung 2 chiều.

### Chương 5: Kết luận và Hướng phát triển (3 – 5 trang)
- Tóm tắt các kết quả đạt được so với mục tiêu ban đầu.
- Những điểm hạn chế còn tồn tại (giới hạn rate-limit API sàn, độ phức tạp của ngôn ngữ chat tự do).
- Hướng mở rộng: Tích hợp mô hình AI phân loại ý định mua hàng tự động, xây dựng nhánh phân tích Data Lakehouse.

---

## 2. NGUYÊN TẮC VĂN PHONG VÀ BẢO VỆ TRƯỚC HỘI ĐỒNG
- **Tuyệt đối tránh văn phong cảm tính**: Sử dụng câu văn khách quan, mệnh đề khoa học.
- **Mọi khẳng định phải có số liệu minh chứng**: Thay vì viết *"hệ thống xử lý rất nhanh"*, phải viết *"hệ thống đạt thời gian phản hồi trung bình 85ms với tỷ lệ lỗi 0% ở mức tải 500 requests/giây"*.
- **Chuẩn bị sẵn câu trả lời phản biện**:
  1. *Làm sao đảm bảo không bị cướp khách trên Facebook?* $\rightarrow$ Trình bày cơ chế Webhook nhận diện SĐT và gọi Graph API ẩn comment tức thì trong <200ms.
  2. *Làm sao không bị mất đơn khi Shoptrack bị sập?* $\rightarrow$ Trình bày cơ chế hàng đợi RabbitMQ với chính sách Retry Exponential Backoff và Dead Letter Queue.

# PTIT GRADUATION THESIS WORKSPACE: HỆ THỐNG GOM ĐƠN ĐA NỀN TẢNG

## 1. ĐỊNH DANH DỰ ÁN & VAI TRÒ AGENT
- **Đề tài**: Xây dựng Hệ thống Gom đơn Đa nền tảng (Multi-channel Order Consolidation Middleware) tích hợp Shoptrack.
- **Vai trò Agent**: Cố vấn Toàn diện ĐATN PTIT (Kỹ sư trưởng Giải pháp Phần mềm & Chủ tịch Hội đồng Chấm ĐATN PTIT).
- **Mục tiêu cốt lõi**:
  1. Thu thập dữ liệu real-time từ 5 kênh (Landing Page, Facebook Fanpage, Zalo OA, Shopee, TikTok Shop).
  2. Bóc tách thông tin khách (Regex/NLP tiếng Việt), tự ẩn comment Facebook chứa SĐT.
  3. Khử trùng khách theo SĐT, map SKU sàn về SKU chuẩn, bảo đảm đơn không bị đẩy trùng (Idempotent).
  4. Đẩy đơn và hội thoại sang Shoptrack, hỗ trợ hộp thư chung 2 chiều.

## 2. QUY CHUẨN KỸ THUẬT BẮT BUỘC (PROJECT RULES)
1. **4 Quy tắc dữ liệu sạch**:
   - *Một khách, một hồ sơ*: Dedup theo số điện thoại (`phone`).
   - *Một sản phẩm, một mã SKU*: Map qua bảng `sku_mappings`.
   - *Một đơn, một lần đẩy*: Idempotent hash theo `source_channel + source_order_id`.
   - *Lỗi thì giữ lại và thử lại*: Sử dụng Retry Queue với Exponential Backoff và Dead Letter Queue.
2. **Kiến trúc hướng sự kiện (Event-driven)**: Hứng Webhook trả về 200 OK ngay trong <100ms, đẩy dữ liệu vào Hàng đợi bất đồng bộ (Redis Queue / ARQ) xử lý ngầm qua worker.
3. **Phân cấp trạng thái đơn**:
   - Đơn Landing Page, Shopee, TikTok: Đủ thông tin $\rightarrow$ Tự động đẩy thẳng vào Shoptrack.
   - Đơn Facebook, Zalo: Dừng ở trạng thái **Đơn nháp (`draft`)**, nhân viên kiểm tra và chốt mới chuyển tiếp.
4. **Tiêu chuẩn học thuật PTIT**:
   - Triệt tiêu bẫy "web CRUD thông thường".
   - Luôn biện luận kiến trúc bằng số liệu đo lường cụ thể (Throughput, Latency, F1-Score).

## 3. DANH MỤC SKILLS HỖ TRỢ
- [order-consolidation](file:///d:/a00_ĐỒ%20ÁN%20TỐT%20NGHIỆP/.agents/skills/order-consolidation/SKILL.md): Quy trình pipeline 4 bước (Ingest, Normalize, Dedup, Push Shoptrack).
- [webhook-integrator](file:///d:/a00_ĐỒ%20ÁN%20TỐT%20NGHIỆP/.agents/skills/webhook-integrator/SKILL.md): Quy chuẩn tích hợp và debug Webhook Meta, Zalo, ngrok.
- [ptit-thesis-writer](file:///d:/a00_ĐỒ%20ÁN%20TỐT%20NGHIỆP/.agents/skills/ptit-thesis-writer/SKILL.md): Hướng dẫn viết báo cáo ĐATN 60–100 trang 5 chương chuẩn PTIT.

# ⚡ SỔ TAY LỆNH NHANH (QUICK RUNBOOK)
> File tổng hợp ngắn gọn tất cả các câu lệnh để khởi động và vận hành hệ thống hàng ngày. Chỉ việc copy và dán vào PowerShell!

---

## 🧭 CÁC ĐỊA CHỈ TRUY CẬP WEB & CỔNG KẾT NỐI (PORT DIRECTORY)

| Dịch vụ / Màn hình | Địa chỉ Web / Cổng | Tài khoản / Cách đăng nhập | Vai trò trong hệ thống |
| :--- | :--- | :--- | :--- |
| 🛍️ **Trang Đặt hàng Landing Page** | [http://localhost:8000](http://localhost:8000) | *Không cần đăng nhập* | Giao diện web bán hàng để khách điền form đặt áo Polo |
| 📖 **Backend Gateway Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | *Không cần đăng nhập* | Xem danh sách API, test gửi request tiếp nhận đơn |
| 🗄️ **Query CSDL Trực quan (pgweb)** | [http://localhost:8081](http://localhost:8081) | Host: `postgres` hoặc `localhost`<br/>Port: `5432` / User: `postgres`<br/>Pass: `StrongPassword@2026`<br/>DB: `gomdon_lakehouse` | Xem & chạy SQL query trực tiếp các bảng `raw_orders`, `customers`, `orders` ngay trên trình duyệt |
| 🐰 **RabbitMQ Management UI** | [http://localhost:15672](http://localhost:15672) | User: `admin`<br/>Pass: `RabbitAdmin@2026` | Xem đồ thị message, theo dõi hàng đợi `orders.inbound.queue` |
| 🏬 **Mock ShopTrack Partner API** | [http://localhost:8001](http://localhost:8001) | Docs: [http://localhost:8001/docs](http://localhost:8001/docs)<br/>Danh sách đơn: [http://localhost:8001/api/v1/orders](http://localhost:8001/api/v1/orders) | Giả lập hệ thống kho đối tác ShopTrack tiếp nhận đơn |
| 🐘 **PostgreSQL Engine (Nội bộ)** | `localhost:5432` | User: `postgres` / DB: `gomdon_lakehouse` | Cổng kết nối CSDL dành cho code Python |
| ⚡ **Redis Engine (Nội bộ)** | `localhost:6379` | Pass: `RedisPass@2026` | Cổng bộ nhớ đệm chống click đúp (SETNX 30s) |
| 📬 **RabbitMQ AMQP (Nội bộ)** | `localhost:5672` | User: `admin` / Pass: `RabbitAdmin@2026` | Cổng giao thức AMQP cho code Python đẩy & hút tin |

---

## 🚀 QUY TRÌNH BẬT HỆ THỐNG ĐỂ LÀM VIỆC (MỞ 4 TAB TERMINAL)

### 📌 TAB 1: BẬT HẠ TẦNG DOCKER (Postgres, Redis, RabbitMQ)
*Chạy 1 lần ở đầu buổi làm việc:*
```powershell
cd "d:\a00_ĐỒ ÁN TỐT NGHIỆP\middleware"

# Bật toàn bộ 3 container chạy ngầm
docker compose up -d

# Kiểm tra trạng thái xem cả 3 đã "Up" chưa
docker compose ps

# Khởi tạo toàn bộ 10 bảng CSDL PostgreSQL (chỉ chạy 1 lần):
python init_db.py
```

*Các lệnh quản lý Docker khi cần:*
```powershell
docker compose stop    # Tạm dừng các container khi nghỉ làm việc
docker compose start   # Bật lại các container đã dừng
docker compose logs -f # Xem dòng log nếu có lỗi
```

---

### 📌 TAB 2: BẬT ĐƯỜNG HẦM CLOUDFLARE (Nhận Webhook)
*Giữ tab này chạy liên tục để duy trì link HTTPS ngoài Internet:*
```powershell
cd "d:\a00_ĐỒ ÁN TỐT NGHIỆP\tools"
.\cloudflared.exe tunnel --url http://localhost:8000
```
*(Bấm `Ctrl + C` để tắt khi không dùng).*

---

### 📌 TAB 3: BẬT BACKEND GATEWAY (Cổng 8000)
*Tiếp nhận đơn hàng, kiểm tra chống spam Redis, lưu kho Bronze và đẩy vào RabbitMQ:*
```powershell
cd "d:\a00_ĐỒ ÁN TỐT NGHIỆP\middleware"

# Kích hoạt môi trường ảo Python
.\.venv\Scripts\Activate.ps1

# Chạy Gateway chính (tự reload khi sửa code):
uvicorn app.main:app --port 8000 --reload
```
*(Bấm `Ctrl + C` để tắt khi không dùng).*

---

### 📌 TAB 4: BẬT CÔNG NHÂN XỬ LÝ (Async Worker)
*Lắng nghe hàng đợi RabbitMQ, khử trùng khách hàng và chuẩn hóa vào Tầng Silver (PostgreSQL):*
```powershell
cd "d:\a00_ĐỒ ÁN TỐT NGHIỆP\middleware"

# Kích hoạt môi trường ảo Python
.\.venv\Scripts\Activate.ps1

# Chạy Worker tiêu thụ thông điệp:
python -m app.workers.order_consumer
```
*(Bấm `Ctrl + C` để tắt khi không dùng).*

---

### 📌 TAB 5: BẬT SERVER GIẢ LẬP SHOPTRACK (Cổng 8001 - Khi cần test đẩy đơn đối tác)
```powershell
cd "d:\a00_ĐỒ ÁN TỐT NGHIỆP\middleware"
.\.venv\Scripts\Activate.ps1
python mock_shoptrack.py
```
*(Bấm `Ctrl + C` để tắt khi không dùng).*

---

## 🛠️ LỆNH DỌN DẸP / KIỂM TRA MÁY

```powershell
# 1. Thu hồi bộ nhớ RAM tạm thời trên Windows (nếu thấy máy bị ăn RAM):
[System.GC]::Collect(); Get-Process | ForEach-Object { try { $_.MinWorkingSet = [IntPtr]::Zero } catch {} }

# 2. Kiểm tra Python & Git:
python --version
git --version
docker --version
```

### Facebook: bản nháp xuyên suốt hội thoại

- Triển khai: chạy `python init_db.py` trước khi khởi động worker mới. Script SQL có thể chạy lại trên DB hiện có; bổ sung `conversation_drafts` và khóa chống trùng `messages.raw_order_id`.
- Bản nháp được lưu ngay cả khi khách chưa có SĐT. Hội thoại mới dùng khóa `page_id:sender_id` để tách fanpage; đơn nháp không còn được tìm chung theo khách hàng. Định danh PSID cũ vẫn được tra cứu để khách quen không phải nhắc lại SĐT. Lịch sử hội thoại cũ không tự động nhập vào nháp mới.
- Tin mới chỉ bổ sung trường có giá trị. Thông tin xung đột được giữ trong `state.issues`, nguồn từng trường nằm trong `state.evidence` (message ID, Bronze ID, nội dung). Không đổi liên kết khách hàng khi khách gửi SĐT khác.
- Xem nháp để tích hợp màn hình nhân viên: `GET /inbound/facebook/drafts/{conversation_id}`. `missing_fields` cho biết dữ liệu thiếu, `issues` chứa đề xuất cần kiểm tra. Đơn Silver luôn ở `draft`, ghi chú yêu cầu nhân viên xác nhận. Endpoint này cần được bảo vệ bằng cơ chế phân quyền của hệ thống triển khai, tương tự các API quản trị hiện có; repo chưa có lớp đăng nhập nhân viên.
- Không tự chọn SKU khi thiếu số lượng/màu/size hoặc biến thể không hỗ trợ. Những câu phức tạp, thay đổi sản phẩm, nhiều sản phẩm và thông tin sản phẩm chia nhỏ cần nhân viên diễn giải từ bằng chứng. Bản nháp giữ các tin này để kiểm tra; chưa tự suy luận mọi cách nói tự nhiên.
- Tin nhắn, bản nháp, đơn và trạng thái Bronze commit cùng giao dịch, khóa theo hội thoại để tránh ghi đè đồng thời; retry cùng Bronze ID không tạo thêm tin/đơn. Khi đơn đã rời trạng thái `draft`, tin tiếp theo mở một chu kỳ nháp mới.
- Kiểm tra: `python -m unittest discover -s tests -v`.

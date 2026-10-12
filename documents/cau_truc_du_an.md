# 📁 BẢN ĐỒ CẤU TRÚC DỰ ÁN (PROJECT STRUCTURE & RUNBOOK)
> **Đề tài**: Xây dựng hệ thống thu thập và chuẩn hóa dữ liệu đơn hàng đa nền tảng  
> **Cập nhật ngày**: 12/10/2026 (Sau khi hoàn tất Giai đoạn 1)  
> **Mục đích**: Bản đồ tra cứu nhanh: file nào nằm ở đâu, vai trò của từng file trong hệ thống, và danh sách những file cũ/thừa có thể dọn dẹp.

---

## 🧭 1. CÂY THƯ MỤC TỔNG QUAN

```text
d:\a00_ĐỒ ÁN TỐT NGHIỆP\
│
├── 📂 documents/                 <-- Tài liệu học thuật, lộ trình và kiểm soát tiến độ
│   ├── roadmap.md                # Lộ trình tổng thể 12 tuần (5 giai đoạn)
│   ├── so_tay_trien_khai_giai_doan_0_1.md  # File kiểm soát toàn diện GĐ 0 & 1 (Gộp mới)
│   └── cau_truc_du_an.md         # File note này (Bản đồ cấu trúc dự án)
│
├── 📂 tools/                     <-- Công cụ bổ trợ ngoại vi
│   └── cloudflared.exe           # Công cụ mở đường hầm HTTPS ra ngoài Internet hứng Webhook
│
├── 📂 .vscode/                   <-- Cấu hình IDE Antigravity
│   └── settings.json             # Cấu hình tự động nhận diện Python Interpreter .venv
│
├── .gitignore                    <-- File quản lý loại trừ Git tập trung duy nhất cho toàn bộ dự án
│
└── 📂 middleware/                <-- SOURCE CODE CHÍNH CỦA HỆ THỐNG GOM ĐƠN
    │
    ├── 📂 app/                   <-- Kiến trúc Backend Module hóa (Chuẩn Task 0.2)
    │   ├── 📂 api/
    │   │   └── inbound.py        # Router tiếp nhận đơn hàng (POST /inbound/landing-page)
    │   ├── 📂 core/
    │   │   ├── config.py         # Đọc và quản lý cấu hình từ file .env
    │   │   ├── database.py       # Quản lý kết nối Database PostgreSQL (psycopg2)
    │   │   ├── redis_client.py   # Client Redis: Chốt khóa chống spam click đúp (SETNX 30s)
    │   │   └── rabbitmq_client.py# Client RabbitMQ: Khởi tạo Exchange, Queue & Publish tin
    │   ├── 📂 schemas/
    │   │   └── order.py          # Pydantic Schemas validate dữ liệu đầu vào & phản hồi
    │   ├── 📂 services/
    │   │   ├── bronze_service.py # Xử lý lưu kho Tầng Bronze (bảng raw_orders)
    │   │   └── silver_service.py # Khử trùng khách hàng (customers) & chuẩn hóa Tầng Silver
    │   ├── 📂 workers/
    │   │   └── order_consumer.py # Async Worker độc lập: Hút tin RabbitMQ, xử lý ngầm
    │   └── main.py               # Entrypoint chính của Gateway FastAPI (Cổng 8000)
    │
    ├── 📂 static/
    │   └── landing_page.html     # Giao diện Web bán hàng responsive (Form đặt hàng)
    │
    ├── 📂 tests/mock_data/       # Bộ 5 file JSON giả lập payload từ các kênh
    │   ├── landing_page_order.json
    │   ├── facebook_webhook_comment.json
    │   ├── facebook_webhook_message.json
    │   ├── zalo_webhook_message.json
    │   └── shopee_order_webhook.json
    │
    ├── docker-compose.yml        # Cấu hình chạy 4 container Docker Alpine (Postgres, Redis, RabbitMQ, pgweb)
    ├── init_db.sql               # Kịch bản SQL khởi tạo 10 bảng CSDL Lakehouse
    ├── init_db.py                # Script chạy tự động nạp init_db.sql vào CSDL
    ├── mock_shoptrack.py         # Server giả lập API ShopTrack (Cổng 8001)
    ├── requirements.txt          # Danh sách thư viện Python của dự án
    ├── README.md                 # Sổ tay lệnh nhanh mở các Tab Terminal hàng ngày
    ├── .env                      # File chứa biến môi trường và mật khẩu kết nối
    └── .env.example              # File mẫu biến môi trường chia sẻ cho đồ án
```

---

## 🔍 2. CHI TIẾT VAI TRÒ TỪNG FILE TRONG HỆ THỐNG

### 🎯 Nhóm 1: Nhóm vận hành Backend chính (`middleware/app/`)
* **`app/main.py`**: Trọng tâm khởi động Gateway tại cổng 8000. Mount trang web `/static` và tự động kiểm tra hạ tầng RabbitMQ khi khởi động.
* **`app/api/inbound.py`**: Cửa ngõ tiếp nhận đơn hàng. Có trách nhiệm: (1) Kiểm tra Redis chống click đúp $\rightarrow$ (2) Ghi bản ghi thô vào Tầng Bronze $\rightarrow$ (3) Bắn tin nhắn vào RabbitMQ $\rightarrow$ (4) Trả về cho khách trong ~140ms.
* **`app/workers/order_consumer.py`**: Công nhân xử lý chạy ngầm. Lắng nghe hàng đợi `orders.inbound.queue`, tự động khử trùng khách theo SĐT và lưu đơn hàng chuẩn hóa vào Tầng Silver trong PostgreSQL.

### 🗄️ Nhóm 2: Nhóm quản lý Dữ liệu & Cơ sở dữ liệu
* **`init_db.sql` & `init_db.py`**: Chứa định nghĩa và lệnh tạo 10 bảng của đồ án trong PostgreSQL (Tầng Bronze, Tầng Silver, Hộp thư chung, Bảng cấu hình và Nhật ký Audit).
* **`docker-compose.yml` (Service `pgweb` - Cổng 8081)**: Công cụ Web UI trực quan hóa CSDL. Thay vì phải gõ lệnh terminal, bạn chỉ cần mở trình duyệt [http://localhost:8081](http://localhost:8081) để xem trực tiếp các bảng `raw_orders`, `customers`, `orders` và chạy SQL query.

### 🧪 Nhóm 3: Nhóm Kiểm thử & Giả lập
* **`static/landing_page.html`**: Trang đặt mua áo Polo mẫu để người dùng thử nghiệm luồng mua hàng và kiểm tra tính năng chặn spam.
* **`mock_shoptrack.py`**: Server giả lập đối tác ShopTrack (cổng 8001), dùng khi nào bạn muốn kích hoạt luồng đẩy đơn ra đối tác bên ngoài.
* **`tests/mock_data/`**: 5 file JSON đại diện cho 5 kênh (Landing Page, Facebook Comment, Facebook Message, Zalo OA, Shopee).

---

## 🗑️ 3. DANH SÁCH FILE ĐÃ DỌN DẸP / KHÔNG CẦN THIẾT

| Tên file | Vị trí | Lý do dọn dẹp | Trạng thái hiện tại |
| :--- | :--- | :--- | :---: |
| **`main_poc.py`** | `middleware/` | File POC tạm sáng nay, đã chuyển toàn bộ sang `app/main.py` & `app/api/inbound.py`. | ✅ **ĐÃ XÓA** |
| **`view_db.py`** | `middleware/` | Đã có Web UI pgweb tại cổng **8081** trực quan và đầy đủ tính năng hơn nhiều. | ✅ **ĐÃ XÓA** |
| **`huong_dan_cai_dat_tech_stack.md`** | `documents/` | Nội dung đã được tinh gọn và cập nhật vào file tổng hợp mới. | ✅ **ĐÃ XÓA** |
| **`tasks_giai_doan_0_va_1.md`** | `documents/` | Nội dung các task và 5 JSON mock payload đã được gom vào file mới. | ✅ **ĐÃ XÓA** |

---

## 💡 4. NGUYÊN TẮC VẬN HÀNH CHUẨN KHI LÀM VIỆC

Khi bạn mở máy làm việc hàng ngày, bạn chỉ cần quan tâm đúng **3 thao tác**:

1. **Khởi động Docker** (nếu chưa chạy):
   ```powershell
   docker compose start
   ```
2. **Bật Gateway** (Terminal 1):
   ```powershell
   uvicorn app.main:app --port 8000 --reload
   ```
3. **Bật Worker** (Terminal 2):
   ```powershell
   python -m app.workers.order_consumer
   ```
4. **Kiểm tra dữ liệu trực quan trên Web (Cổng 8081)**:
   * Mở trình duyệt vào: **[http://localhost:8081](http://localhost:8081)**
   * Đăng nhập (Host: `postgres` hoặc `localhost`, User: `postgres`, Pass: `StrongPassword@2026`, DB: `gomdon_lakehouse`)
   * Click vào thanh bên trái để kiểm tra trực tiếp các bảng:
     * `raw_orders`: Xem dữ liệu JSON thô Tầng Bronze đã được lưu trữ.
     * `customers`: Xem hồ sơ khách hàng đã được khử trùng theo SĐT.
     * `orders` & `order_items`: Xem đơn hàng chuẩn hóa Tầng Silver.

---

## 🌐 5. DANH MỤC CỔNG & ĐỊA CHỈ TRUY CẬP (PORT DIRECTORY)

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

## 🔄 6. SƠ ĐỒ LUỒNG DỮ LIỆU & VAI TRÒ TỪNG FILE PYTHON

### 1. Landing Page gửi URL/API đến file nào?
* Khi khách bấm **"Đặt hàng ngay"** trên trình duyệt:
  * Mã JavaScript trong `static/landing_page.html` gửi request:  
    👉 **`POST http://localhost:8000/inbound/landing-page`**
  * Luồng tiếp nhận ở Backend:
    1. **`app/main.py`**: Web server cổng 8000 đón request đầu tiên và chuyển tiếp tới router.
    2. 👉 **`app/api/inbound.py`** (hàm `receive_landing_page_order`): **File tiếp nhận trực tiếp dữ liệu từ Landing Page.**
    3. Cấu trúc dữ liệu được kiểm tra bằng khuôn mẫu tại **`app/schemas/order.py`** (`LandingPageOrderIn`).

### 2. Dữ liệu từ Bronze được xử lý ở file nào để sang Silver?
* **Bước 1 (Ghi vào Bronze)**:
  * `app/api/inbound.py` gọi `app/services/bronze_service.py` để lưu nguyên vẹn JSON thô vào bảng **`raw_orders`** (Tầng Bronze).
  * Sau đó gọi `app/core/rabbitmq_client.py` để bắn message vào hàng đợi RabbitMQ và phản hồi cho web trong ~140ms.
* **Bước 2 (Chuyển đổi sang Silver)**:
  * 👉 **File xử lý chính**: **`app/workers/order_consumer.py`** (Worker chạy ngầm độc lập).
  * Worker lắng nghe queue `orders.inbound.queue`, khi có đơn sẽ gọi:  
    👉 **`app/services/silver_service.py`**:
    * Hàm `get_or_create_customer()`: Khử trùng khách hàng theo SĐT trong bảng **`customers`** (*"Một khách - Một hồ sơ"*).
    * Hàm `create_silver_order()`: Chuẩn hóa đơn hàng (mã `ORD_20261012_...`), lưu vào bảng **`orders`** và **`order_items`** (Tầng Silver).
  * Worker gọi lại `bronze_service.py` để cập nhật trạng thái bản ghi Bronze từ `'pending'` sang `'processed'`.

### 3. Hình vẽ trực quan toàn bộ luồng đi dữ liệu (Dạng sơ đồ khối)

```text
====================================================================================================
                        SƠ ĐỒ LUỒNG ĐI DỮ LIỆU TỪ LANDING PAGE ĐẾN LAKEHOUSE
====================================================================================================

 [ TRÌNH DUYỆT CỦA KHÁCH ]
         │
         │  (1) Bấm Đặt hàng: POST /inbound/landing-page (Kèm JSON tên, SĐT, áo)
         ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ 1. FASTAPI GATEWAY (app/main.py -> app/api/inbound.py)                                 │
 │                                                                                        │
 │   • Bước A: Gọi app/core/redis_client.py                                               │
 │             Chốt khóa Redis SETNX (30s) -> Nếu bấm đúp liên tiếp thì chặn ngay!        │
 │                                                                                        │
 │   • Bước B: Gọi app/services/bronze_service.py                                         │
 │             Lưu nguyên văn JSON thô vào CSDL PostgreSQL                                │
 │             ──────────────► [ TẦNG BRONZE: Bảng raw_orders (ID #..., pending) ]        │
 │                                                                                        │
 │   • Bước C: Gọi app/core/rabbitmq_client.py                                            │
 │             Bắn message vào hàng đợi RabbitMQ                                          │
 └───────────────────────────────────┬────────────────────────────────────────────────────┘
         │                           │
         │ (2) Trả về cho Web:       │ (3) Bắn tin nhắn đơn hàng vào Queue
         │ "Đã tiếp nhận! (140ms)"   ▼
         │                 ┌───────────────────────────────────┐
         ▼                 │ 2. HÀNG ĐỢI AMQP RABBITMQ         │
   [ WEB BÁO XANH ]        │ (Queue: orders.inbound.queue)     │
                           └─────────────────┬─────────────────┘
                                             │
                                             │ (4) Worker tự động hút tin nhắn ra
                                             ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ 3. ASYNC WORKER CHẠY NGẦM (app/workers/order_consumer.py)                              │
 │                                                                                        │
 │   • Bước D: Gọi app/services/silver_service.py                                         │
 │             Khử trùng khách theo SĐT                                                   │
 │             ──────────────► [ TẦNG SILVER: Bảng customers ]                            │
 │                                                                                        │
 │   • Bước E: Gọi app/services/silver_service.py                                         │
 │             Bóc tách đơn hàng chuẩn hóa (Mã ORD_...)                                   │
 │             ──────────────► [ TẦNG SILVER: Bảng orders & order_items ]                 │
 │                                                                                        │
 │   • Bước F: Đổi cờ raw_orders từ 'pending' -> 'processed'                              │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4. Bảng tra cứu vai trò từng file `.py` trong hệ thống

| Tên file `.py` | Vai trò thực tế trong hệ thống | Tương đương trong đời sống |
| :--- | :--- | :--- |
| **`app/main.py`** | Máy chủ gốc chạy cổng 8000, quản lý router và static web | **Lễ tân tòa nhà** (Đón khách, điều hướng) |
| **`app/api/inbound.py`** | Tiếp nhận POST từ Landing Page, chặn click đúp, điều phối | **Cửa khẩu tiếp nhận hàng** |
| **`app/schemas/order.py`** | Pydantic định nghĩa cấu trúc dữ liệu hợp lệ (tên, SĐT, giá) | **Biểu mẫu kiểm tra hợp lệ** |
| **`app/core/config.py`** | Đọc các biến môi trường, mật khẩu, IP từ `.env` | **Sổ danh bạ cấu hình** |
| **`app/core/database.py`** | Quản lý đóng/mở kết nối tới PostgreSQL an toàn | **Đường ống dẫn tới kho dữ liệu** |
| **`app/core/redis_client.py`** | Khóa chống click đúp `SETNX` trong 30 giây | **Thanh chắn barie chống bấm dồn** |
| **`app/core/rabbitmq_client.py`** | Khởi tạo Exchange, Queue và đưa tin nhắn vào RabbitMQ | **Bưu điện đóng gói phát thư** |
| **`app/services/bronze_service.py`** | Lưu và cập nhật bảng `raw_orders` | **Thủ kho ghi sổ nguyên bản (Tầng Bronze)** |
| **`app/services/silver_service.py`** | Khử trùng khách hàng và tạo đơn sạch `orders` | **Tổ phân loại & chuẩn hóa hàng (Tầng Silver)** |
| **`app/workers/order_consumer.py`** | Chạy ngầm 24/7 hút đơn từ RabbitMQ để đưa sang Silver | **Công nhân phân loại bốc xếp tự động** |

# 🏥 Bệnh Viện Đa Khoa ATus - Hệ Thống Y Tế Thông Minh 3D & Hàng Đợi Đa Phân Hệ

Hệ thống ứng dụng Y tế Thông minh kết hợp AI tiếp đón, mô hình bệnh viện 3D trực quan, cấp số thứ tự theo từng phòng khám và điều phối luồng cận lâm sàng khép kín trên **Microsoft SQL Server (Database: `hospital_atus`)**.

---

## 🌟 Kiến Trúc Độc Lập - Tách Biệt Rõ Ràng Từng Cổng Ứng Dụng

Hệ thống được chia thành **3 ứng dụng giao diện riêng biệt** và **1 máy chủ REST API**, bảo mật tuyệt đối, không để chung luồng:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          HỆ THỐNG PHÂN HỆ ATUS HOSPITAL                         │
├──────────────────┬──────────────────┬──────────────────┬────────────────────────┤
│ 1. CỔNG BỆNH NHÂN│ 2. CỔNG NHÂN VIÊN│ 3. CỔNG QUẢN TRỊ │ 4. REST API CHUẨN      │
│  (app_user.py)   │  (app_staff.py)  │  (app_admin.py)  │    (api_server.py)     │
├──────────────────┼──────────────────┼──────────────────┼────────────────────────┤
│ • Dành cho Kiosk │ • Dành cho:      │ • Dành cho:      │ • Swagger UI Docs:     │
│   sảnh tiếp đón  │   - Bác sĩ khám  │   - Admin viện   │   localhost:8000/docs  │
│ • Không đăng nhập│   - KTV xét nghiệm   - Trưởng khoa  │ • Cho Mobile/Kiosk app │
│ • AI Voice/3D    │ • Phân luồng y tế│ • Giám sát real- │ • Kết nối HIS/EMR      │
│ • Cấp số khám    │ • Cận lâm sàng   │   time toàn viện │   chuẩn quốc tế        │
│ • Nhận SMS       │ • Đọc kết quả    │ • Audit Logs/KPI │                        │
└──────────────────┴──────────────────┴──────────────────┴────────────────────────┘
                                      │
                                      ▼
                      MICROSOFT SQL SERVER: hospital_atus
```

---

## 🚀 Hướng Dẫn Khởi Chạy Từng Ứng Dụng

Kích hoạt môi trường ảo:
- Nếu dùng PowerShell: `.\venv\Scripts\Activate.ps1` (hoặc `.venv\Scripts\Activate.ps1`)
- Hoặc dùng trực tiếp Python của môi trường: `.\venv\Scripts\python.exe` / `.\venv\Scripts\streamlit.exe`

### 1. Cổng Kiosk Bệnh Nhân (Port 8501)
```bash
streamlit run app_user.py --server.port 8501
```
*Truy cập tại: `http://localhost:8501`*  
- Bệnh nhân chat với AI tư vấn bằng chữ hoặc giọng nói tiếng Việt.
- Mô hình 3D tự động xoay và zoom vào phòng khám được đề xuất.
- Điền thông tin lấy số thứ tự theo phòng (mã `PK301-xxx`, `PK302-xxx`), nhận tin nhắn SMS xác nhận.

---

### 2. Cổng Nhân Viên Y Tế (Bác Sĩ & Kỹ Thuật Viên) (Port 8502)
```bash
streamlit run app_staff.py --server.port 8502
```
*Truy cập tại: `http://localhost:8502`*  
- **Bác sĩ**: Đăng nhập xem hàng đợi phòng mình, gọi số, khám bệnh, ra chỉ định cận lâm sàng (lấy máu, đo hô hấp, X-Quang, MRI...).
- **Kỹ thuật viên**: Tiếp nhận bệnh nhân được chuyển đến, thực hiện dịch vụ, nhập kết quả và **tự động trả bệnh nhân về lại phòng khám ban đầu với cờ Ưu Tiên ⭐**.

---

### 3. Cổng Quản Trị Hệ Thống & Giám Sát (Port 8503)
```bash
streamlit run app_admin.py --server.port 8503
```
*Truy cập tại: `http://localhost:8503`*  
- Giám sát tình trạng hàng đợi của toàn bộ 12 phòng khám và cận lâm sàng theo thời gian thực.
- Báo cáo phân tích KPI, biểu đồ Intent, chuyên khoa và ca cảnh báo khẩn cấp.
- Quản lý danh sách người dùng và nhật ký an toàn y tế (**Audit Trail**).

---

### 4. Máy Chủ REST API Độc Lập (Port 8000)
```bash
python api_server.py
```
- Base URL: `http://localhost:8000`
- **Tài liệu Swagger UI tương tác trực tiếp:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 👥 Danh Sách Tài Khoản Mẫu Theo Từng Cổng

| Cổng ứng dụng | Tên đăng nhập | Mật khẩu | Họ tên | Vai trò & Phạm vi |
|---|---|---|---|---|
| **Cổng Kiosk (8501)** | *(Không cần)* | *(Không cần)* | Bệnh nhân tại sảnh | Bệnh nhân / Người nhà |
| **Cổng Nhân viên (8502)** | `bsi_mat` | `123456` | BS. CKI Trần Thị Mắt | Bác sĩ - Phòng 302 (Khoa Mắt) |
| **Cổng Nhân viên (8502)** | `bsi_noi` | `123456` | BS. ThS Nguyễn Văn Nội | Bác sĩ - Phòng 301 (Nội Tổng Quát) |
| **Cổng Nhân viên (8502)** | `ktv_mau` | `123456` | KTV. Lê Thị Lấy Máu | KTV - Phòng 201 (Lấy Máu & XN) |
| **Cổng Nhân viên (8502)** | `ktv_hohap` | `123456` | KTV. Phạm Văn Đo Hô Hấp | KTV - Phòng 202 (Đo Chức Năng Hô Hấp) |
| **Cổng Quản trị (8503)** | `admin` | `admin123` | Quản Trị Viên Hệ Thống | Toàn quyền quản trị hệ thống |
| **Cổng Quản trị (8503)** | `qly_khoanoi` | `123456` | TS. BS Hoàng Trưởng Khoa | Trưởng Khoa Khám Bệnh |

---

## 🔄 Luồng Nghiệp Vụ Cận Lâm Sàng Khép Kín

```mermaid
flowchart TD
    A["Bệnh nhân tại Kiosk (app_user.py)"] -->|AI gợi ý & Lấy số| B["Hàng đợi Phòng Khám (VD: PK302-001)"]
    B -->|Bác sĩ gọi số & Khám (app_staff.py)| C["Bác sĩ chỉ định Cận lâm sàng"]
    C -->|Tự động cấp số CLS & Đổi phòng| D["Hàng đợi Phòng CLS (VD: HH202-001)"]
    D -->|KTV thực hiện & Nhập kết quả| E["Hoàn thành Cận lâm sàng"]
    E -->|Tự động trả về với cờ Ưu tiên ⭐| F["Quay lại Phòng Khám Ban đầu (Ưu tiên)"]
    F -->|Bác sĩ đọc kết quả & Kết luận| G["Hoàn thành lượt khám xuất viện"]
```

---

## 📁 Cấu Trúc Mã Nguồn Sau Khi Tách Biệt

```
hospital-assistant/
├── app_user.py                     # [PORT 8501] Cổng Kiosk Bệnh Nhân (Tiếp đón AI + 3D + Lấy số)
├── app_staff.py                    # [PORT 8502] Cổng Nhân Viên Y Tế (Bác sĩ + KTV Cận lâm sàng)
├── app_admin.py                    # [PORT 8503] Cổng Quản Trị Viên & Trưởng Khoa (Giám sát + Audit)
├── api_server.py                   # [PORT 8000] Máy chủ REST API FastAPI + Swagger UI Docs (/docs)
├── db.py                           # Module kết nối Microsoft SQL Server (database: hospital_atus)
├── db_schema.sql                   # Kịch bản DDL tạo 7 bảng SQL Server
├── seed_data.py                    # Nạp dữ liệu mẫu phòng khám, nhân viên & migrate dữ liệu
├── auth.py                         # Xác thực PBKDF2-SHA256, Audit Trail, chống Brute-force
├── queue_service.py                # Cấp số, gọi số, chỉ định CLS & điều phối luân chuyển bệnh nhân
├── assistant.py                    # Hub điều phối AI Triage, Emergency, RAG & Mô hình 3D
├── triage.py                       # Phân loại triệu chứng & gợi ý chuyên khoa
├── rag.py                          # RAG ngữ nghĩa (Gemini Embedding + FAISS + MMR)
├── sms_service.py                  # Dịch vụ gửi tin nhắn SMS Brandname
├── analytics.py                    # Thống kê phân tích số liệu
└── requirements.txt                # Danh sách thư viện (pyodbc, fastapi, uvicorn, streamlit, faiss...)
```

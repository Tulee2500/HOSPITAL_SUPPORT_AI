"""Hệ thống REST API độc lập cho Bệnh Viện Đa Khoa ATus.
Cung cấp các endpoints chuẩn cho Kiosk, Bác Sĩ, Kỹ Thuật Viên Cận Lâm Sàng, Quản Lý & Admin.
Tài liệu tương tác tự động Swagger UI tại: http://localhost:8000/docs
"""
from __future__ import annotations

from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
import queue_service
import auth
from assistant import answer
from sms_service import send_appointment_sms
from analytics import get_analytics_summary

app = FastAPI(
    title="🏥 ATUS Hospital Smart API",
    description="Hệ thống API Tiếp Đón AI, Cấp Số Thứ Tự & Điều Phối Bệnh Viện Đa Khoa ATus (5 Tầng)",
    version="2.0.0"
)

# Kích hoạt CORS để Web Frontend, Kiosk hoặc Mobile gọi trực tiếp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────── Pydantic Request Models ──────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)

class IssueTicketRequest(BaseModel):
    room_id: int
    patient_name: str
    patient_phone: str
    patient_notes: Optional[str] = ""
    send_sms: bool = True

class CallTicketRequest(BaseModel):
    room_id: int
    user_id: int
    username: str

class StartExamRequest(BaseModel):
    ticket_id: int
    user_id: int
    username: str

class CreateOrderRequest(BaseModel):
    ticket_id: int
    doctor_id: int
    doctor_username: str
    clinic_room_id: int
    target_room_id: int
    order_type: str  # blood_test, respiratory_test, xray, mri, other
    order_name: str
    notes: Optional[str] = ""

class CompleteOrderRequest(BaseModel):
    order_id: int
    technician_id: int
    technician_username: str
    results: Optional[str] = ""

class FinishTicketRequest(BaseModel):
    ticket_id: int
    user_id: int
    username: str


# ────────────────────────── 1. NHÓM API XÁC THỰC (AUTH) ──────────────────────
@app.post("/api/auth/login", tags=["Xác Thực (Authentication)"], summary="Đăng nhập tài khoản nhân viên")
def login(req: LoginRequest):
    """Đăng nhập Bác sĩ, KTV, Quản lý, Admin. Hỗ trợ khóa tài khoản chống Brute-force."""
    res = auth.authenticate_user(req.username, req.password)
    if not res["success"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=res["error"])
    return res


# ────────────────────────── 2. NHÓM API KIOSK BỆNH NHÂN ──────────────────────
@app.get("/api/kiosk/rooms", tags=["Kiosk Bệnh Nhân"], summary="Danh sách phòng khám tiếp đón")
def get_kiosk_rooms():
    """Lấy danh sách các phòng khám lâm sàng phục vụ cấp số tại kiosk."""
    return {"rooms": queue_service.get_all_rooms(room_type="clinic")}

@app.post("/api/kiosk/chat", tags=["Kiosk Bệnh Nhân"], summary="Hỏi đáp AI tiếp đón & gợi ý chuyên khoa")
def chat_ai(req: ChatRequest):
    """Chatbot AI tiếp đón phân luồng triệu chứng, giải đáp BHYT và định vị 3D."""
    reply = answer(req.message, history=req.history)
    # Nếu là generator stream -> gom chuỗi text để trả JSON qua REST API
    text_content = reply["text"]
    if reply.get("stream"):
        text_content = "".join(list(reply["stream"]))
    
    return {
        "type": reply["type"],
        "text": text_content,
        "department": reply.get("department"),
        "location": reply.get("location"),
        "sources": reply.get("sources", [])
    }

@app.post("/api/kiosk/issue-ticket", tags=["Kiosk Bệnh Nhân"], summary="Bệnh nhân lấy số thứ tự tại phòng khám")
def issue_ticket(req: IssueTicketRequest):
    """Cấp số thứ tự theo từng phòng khám, reset theo ngày. Gửi SMS Brandname nếu yêu cầu."""
    try:
        ticket = queue_service.issue_ticket(
            room_id=req.room_id,
            patient_name=req.patient_name.strip(),
            patient_phone=req.patient_phone.strip(),
            patient_notes=req.patient_notes.strip() if req.patient_notes else ""
        )
        # Gửi tin nhắn SMS xác nhận nếu người dùng chọn
        sms_info = None
        if req.send_sms and req.patient_phone.strip():
            sms_info = send_appointment_sms(
                code=ticket["ticket_number"],
                name=ticket["patient_name"],
                phone=ticket["patient_phone"],
                dept=ticket["room_name"],
                date=ticket["created_at"].split()[0]
            )

        return {
            "success": True,
            "ticket": ticket,
            "sms": sms_info
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ────────────────────────── 3. NHÓM API HÀNG ĐỢI & PHÒNG KHÁM ────────────────
@app.get("/api/queue/{room_id}", tags=["Hàng Đợi (Queues)"], summary="Lấy danh sách hàng đợi của phòng")
def get_room_queue(room_id: int):
    """Lấy danh sách bệnh nhân đang gọi, đang khám, và đang chờ của 1 phòng cụ thể."""
    return queue_service.get_room_queue(room_id)

@app.post("/api/queue/call-next", tags=["Hàng Đợi (Queues)"], summary="Gọi bệnh nhân tiếp theo vào phòng")
def call_next(req: CallTicketRequest):
    """Bác sĩ hoặc KTV bấm gọi số tiếp theo. Tự động ưu tiên bệnh nhân vừa xong cận lâm sàng quay lại."""
    called = queue_service.call_next_patient(req.room_id, req.user_id, req.username)
    if not called:
        return {"success": False, "message": "Hàng đợi phòng hiện đang trống!"}
    return {"success": True, "patient": called}

@app.post("/api/queue/start-exam", tags=["Hàng Đợi (Queues)"], summary="Bắt đầu khám / bắt đầu thực hiện")
def start_exam(req: StartExamRequest):
    success = queue_service.start_exam(req.ticket_id, req.user_id, req.username)
    return {"success": success}

@app.post("/api/queue/complete", tags=["Hàng Đợi (Queues)"], summary="Hoàn thành lượt khám xuất viện")
def complete_exam(req: FinishTicketRequest):
    success = queue_service.complete_ticket(req.ticket_id, req.user_id, req.username)
    return {"success": success}

@app.post("/api/queue/skip", tags=["Hàng Đợi (Queues)"], summary="Bỏ qua lượt bệnh nhân vắng mặt")
def skip_exam(req: FinishTicketRequest):
    success = queue_service.skip_ticket(req.ticket_id, req.user_id, req.username)
    return {"success": success}


# ────────────────────────── 4. NHÓM API ĐIỀU PHỐI CẬN LÂM SÀNG ───────────────
@app.get("/api/paraclinical/rooms", tags=["Cận Lâm Sàng"], summary="Danh sách phòng cận lâm sàng (máu, hô hấp, X-Quang)")
def get_paraclinical_rooms():
    return {"rooms": queue_service.get_all_rooms(room_type="paraclinical")}

@app.post("/api/paraclinical/orders", tags=["Cận Lâm Sàng"], summary="Bác sĩ ra chỉ định cận lâm sàng cho bệnh nhân")
def create_cls_order(req: CreateOrderRequest):
    """Tự động cấp số tại phòng cận lâm sàng và chuyển bệnh nhân sang hàng đợi phòng đó."""
    try:
        res = queue_service.create_clinical_order(
            ticket_id=req.ticket_id,
            doctor_id=req.doctor_id,
            doctor_username=req.doctor_username,
            clinic_room_id=req.clinic_room_id,
            target_room_id=req.target_room_id,
            order_type=req.order_type,
            order_name=req.order_name,
            notes=req.notes or ""
        )
        return {"success": True, "order": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/paraclinical/complete-order", tags=["Cận Lâm Sàng"], summary="KTV hoàn thành chỉ định và trả bệnh nhân về phòng khám")
def finish_cls_order(req: CompleteOrderRequest):
    """Đánh dấu hoàn thành xét nghiệm, tự động đưa bệnh nhân quay lại hàng đợi phòng khám ban đầu với quyền ưu tiên."""
    try:
        res = queue_service.complete_cls_order(
            order_id=req.order_id,
            technician_id=req.technician_id,
            technician_username=req.technician_username,
            results=req.results or ""
        )
        return {"success": True, "return_info": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ────────────────────────── 5. NHÓM API QUẢN TRỊ & THỐNG KÊ ──────────────────
@app.get("/api/admin/analytics", tags=["Quản Trị & Thống Kê"], summary="Số liệu KPI và thống kê toàn viện")
def get_admin_analytics():
    return get_analytics_summary()

@app.get("/api/admin/audit-logs", tags=["Quản Trị & Thống Kê"], summary="Nhật ký kiểm toán an toàn y tế")
def get_audit_logs(limit: int = Query(50, le=200)):
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP (?) id, user_id, username, action, target_type, target_id, details, ip_address, created_at
            FROM audit_logs
            ORDER BY id DESC
        """, (limit,))
        cols = [column[0] for column in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        return {"logs": rows}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    print("🚀 Khởi chạy máy chủ API tại http://localhost:8000 (Tài liệu Swagger: http://localhost:8000/docs)")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)

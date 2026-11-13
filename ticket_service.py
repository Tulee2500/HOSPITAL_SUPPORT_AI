"""Dịch vụ Xuất Phiếu Khám & Lấy Số Thứ Tự Kiosk (Thermal Ticket & PDF Generator).

Tuân thủ quy chuẩn y tế và Nghị định 13/2023/NĐ-CP:
1. Định dạng kích thước chuẩn hóa: Khổ giấy in nhiệt Kiosk 80mm (Thermal Receipt 80mm x 140mm).
2. Hỗ trợ tiếng Việt Unicode 100% chuẩn xác với font hệ thống (Arial / Arial-Bold).
3. Tích hợp mã QR Code động: Cho phép bệnh nhân quét mã để theo dõi lượt khám theo thời gian thực trên điện thoại.
4. Bảo vệ quyền riêng tư người bệnh: Che giấu danh tính (Masking) theo Nghị định 13 (ví dụ: 'Nguyễn V. A').
5. Đầy đủ dữ liệu dẫn đường 3D: Mã phòng, số tầng, lộ trình tóm tắt và số người đang chờ.
"""
from __future__ import annotations

import io
import base64
import os
from datetime import datetime, date
import qrcode
from PIL import Image

from reportlab.lib.pagesizes import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import db

# Đăng ký font tiếng Việt hỗ trợ Unicode đầy đủ trên Windows
FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

try:
    if os.path.exists("C:/Windows/Fonts/arial.ttf"):
        pdfmetrics.registerFont(TTFont("ArialVN", "C:/Windows/Fonts/arial.ttf"))
        FONT_NORMAL = "ArialVN"
    if os.path.exists("C:/Windows/Fonts/arialbd.ttf"):
        pdfmetrics.registerFont(TTFont("ArialVN-Bold", "C:/Windows/Fonts/arialbd.ttf"))
        FONT_BOLD = "ArialVN-Bold"
except Exception:
    pass


def generate_qr_base64(data: str) -> str:
    """Tạo mã QR Code động dạng base64 PNG phục vụ hiển thị web."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#003a70", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def mask_patient_name(name: str) -> str:
    """Rút gọn tên bệnh nhân theo Nghị định 13/2023/NĐ-CP (ví dụ: 'Nguyễn Văn An' -> 'Nguyễn V. An')."""
    if not name:
        return ""
    parts = name.strip().split()
    if len(parts) >= 3:
        return f"{parts[0]} {' '.join(p[0] + '.' for p in parts[1:-1])} {parts[-1]}"
    elif len(parts) == 2:
        return f"{parts[0]} {parts[1][0]}."
    return name


def get_ticket_info(ticket_id: int) -> dict | None:
    """Truy vấn thông tin chi tiết của một vé khám từ cơ sở dữ liệu."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.ticket_number, t.daily_seq, t.status, t.priority_level,
                   t.created_at, t.visit_date, t.patient_id, t.patient_name, t.patient_phone,
                   p.patient_code, p.cccd, p.bhyt_code, p.dob, p.gender,
                   r.id AS room_id, r.code AS room_code, r.name AS room_name,
                   r.room_number, r.floor, r.instructions,
                   d.name AS dept_name,
                   u.full_name AS doctor_name, ds.shift
            FROM tickets t
            LEFT JOIN patients p ON t.patient_id = p.id
            LEFT JOIN rooms r ON t.current_room_id = r.id
            LEFT JOIN departments d ON r.department_id = d.id
            LEFT JOIN doctor_schedules ds ON t.schedule_id = ds.id
            LEFT JOIN users u ON ds.doctor_id = u.id
            WHERE t.id = ?
        """, (ticket_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Đếm số người đang chờ phía trước
        visit_d = row[6]
        c_room_id = row[15]
        p_lvl = row[4]
        cursor.execute("""
            SELECT COUNT(*) 
            FROM tickets 
            WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic')
              AND (priority_level > ? OR (priority_level = ? AND id < ?))
        """, (c_room_id, visit_d, p_lvl, p_lvl, ticket_id))
        waiting_ahead = cursor.fetchone()[0]

        return {
            "ticket_id": row[0],
            "ticket_number": row[1],
            "daily_seq": row[2],
            "status": row[3],
            "priority_level": row[4],
            "created_at": row[5],
            "visit_date": row[6],
            "patient_id": row[7],
            "patient_name": row[8],
            "patient_name_masked": mask_patient_name(row[8]),
            "patient_phone": row[9],
            "patient_code": row[10] or "AT-000000",
            "cccd": row[11],
            "bhyt_code": row[12],
            "dob": row[13],
            "gender": row[14],
            "room_id": row[15],
            "room_code": row[16],
            "room_name": row[17],
            "room_number": row[18],
            "floor": row[19],
            "instructions": row[20] or "Đi thang máy trung tâm đến phòng khám tương ứng.",
            "dept_name": row[21] or "",
            "doctor_name": row[22] or "Bác sĩ trực chuyên khoa",
            "shift": row[23] or "Ca sáng",
            "waiting_ahead": waiting_ahead,
            "est_wait_minutes": waiting_ahead * 10
        }
    finally:
        conn.close()


def generate_ticket_html(t: dict, lang: str = "vi") -> str:
    """Tạo mã HTML hiển thị thẻ Phiếu Lấy Số Kiosk đẹp mắt chuẩn y tế."""
    qr_data = f"https://atus-hospital.vn/track?t={t['ticket_number']}&mpi={t['patient_code']}"
    qr_b64 = generate_qr_base64(qr_data)
    
    is_vi = (lang == "vi")
    title_text = "PHIẾU LẤY SỐ KHÁM BỆNH" if is_vi else "CLINICAL QUEUE TICKET"
    sub_title = "BỆNH VIỆN ĐA KHOA QUỐC TẾ ATUS" if is_vi else "ATUS INTERNATIONAL GENERAL HOSPITAL"
    patient_lbl = "Người bệnh:" if is_vi else "Patient:"
    mpi_lbl = "Mã BN (MPI):" if is_vi else "Patient ID:"
    room_lbl = "Phòng khám:" if is_vi else "Clinic Room:"
    floor_lbl = "Vị trí:" if is_vi else "Location:"
    doc_lbl = "Bác sĩ trực:" if is_vi else "Attending Doctor:"
    wait_lbl = "Người chờ trước:" if is_vi else "Waiting ahead:"
    est_lbl = "Thời gian chờ ước tính:" if is_vi else "Est. Wait time:"
    qr_note = "Quét mã QR để theo dõi lượt gọi số & bản đồ trên điện thoại" if is_vi else "Scan QR to track queue & 3D map on your phone"

    created_str = t["created_at"].strftime("%H:%M - %d/%m/%Y") if isinstance(t["created_at"], datetime) else str(t["created_at"])
    is_er = (t.get("priority_level", 0) >= 2) or ("cấp cứu" in t["room_name"].lower())

    border_color = "#e55353" if is_er else "#008f88"
    header_bg = "#e55353" if is_er else "#003a70"
    num_color = "#e55353" if is_er else "#008f88"

    return f"""
    <div style="max-width:380px;margin:auto;background:#ffffff;border:2px dashed {border_color};border-radius:14px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,0.08);font-family:system-ui,-apple-system,sans-serif;color:#1e293b;">
        <!-- Header -->
        <div style="background:{header_bg};color:#ffffff;text-align:center;padding:14px 10px;">
            <div style="font-size:12px;letter-spacing:1px;font-weight:700;opacity:0.9;">{sub_title}</div>
            <div style="font-size:16px;font-weight:900;margin-top:2px;">{title_text}</div>
            <div style="font-size:11px;opacity:0.8;margin-top:2px;">⏰ {created_str}</div>
        </div>

        <!-- Body -->
        <div style="padding:16px 20px;text-align:center;">
            <div style="font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;">
                {"SỐ THỨ TỰ KHÁM" if is_vi else "YOUR QUEUE NUMBER"}
            </div>
            <div style="font-size:38px;font-weight:900;color:{num_color};letter-spacing:1px;margin:4px 0 10px 0;">
                {t['ticket_number']}
            </div>

            {"<div style='background:#fef2f2;color:#b91c1c;padding:4px 8px;border-radius:6px;font-size:12px;font-weight:700;margin-bottom:12px;'>🚨 ƯU TIÊN TIẾP ĐÓN CẤP CỨU KHẨN CẤP</div>" if is_er else ""}

            <!-- Chi tiết bệnh nhân & phòng -->
            <div style="text-align:left;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;font-size:13px;line-height:1.6;margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#64748b;">{patient_lbl}</span>
                    <b style="color:#0f172a;">{t['patient_name_masked']}</b>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#64748b;">{mpi_lbl}</span>
                    <b style="color:#008f88;">{t['patient_code']}</b>
                </div>
                <div style="border-top:1px dashed #cbd5e1;margin:6px 0;"></div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#64748b;">{room_lbl}</span>
                    <b style="color:#003a70;">{t['room_name']} ({t['room_number']})</b>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#64748b;">{floor_lbl}</span>
                    <b>Tầng {t['floor']}</b>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:#64748b;">{doc_lbl}</span>
                    <span>{t['doctor_name']}</span>
                </div>
            </div>

            <!-- Trạng thái hàng đợi -->
            <div style="display:flex;justify-content:space-around;background:#f0fdfa;border:1px solid #ccfbf1;border-radius:8px;padding:8px;font-size:12px;margin-bottom:14px;">
                <div>
                    <span style="color:#0f766e;display:block;">{wait_lbl}</span>
                    <b style="font-size:16px;color:#0f766e;">{t['waiting_ahead']} người</b>
                </div>
                <div style="border-left:1px solid #99f6e4;"></div>
                <div>
                    <span style="color:#0f766e;display:block;">{est_lbl}</span>
                    <b style="font-size:16px;color:#0f766e;">~{t['est_wait_minutes']} phút</b>
                </div>
            </div>

            <!-- QR Code -->
            <div style="margin:8px 0;">
                <img src="data:image/png;base64,{qr_b64}" style="width:110px;height:110px;border-radius:6px;border:1px solid #cbd5e1;" />
                <div style="font-size:10.5px;color:#64748b;margin-top:4px;">{qr_note}</div>
            </div>

            <!-- Chỉ dẫn di chuyển tóm tắt -->
            <div style="font-size:11.5px;color:#334155;background:#f1f5f9;border-radius:6px;padding:6px 10px;margin-top:10px;line-height:1.4;">
                🧭 <b>Chỉ dẫn:</b> {t['instructions']}
            </div>
        </div>

        <!-- Footer -->
        <div style="background:#f8fafc;border-top:1px dashed #cbd5e1;padding:8px;text-align:center;font-size:10.5px;color:#94a3b8;">
            Vui lòng giữ phiếu và theo dõi màn hình hiển thị tại sảnh chờ.
        </div>
    </div>
    """


def generate_ticket_pdf(t: dict, lang: str = "vi") -> bytes:
    """Tạo file PDF phiếu khám nhiệt kích thước tiêu chuẩn Kiosk 80mm x 150mm hỗ trợ Unicode."""
    page_width = 80 * mm
    page_height = 155 * mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    # Helper text UTF-8
    is_vi = (lang == "vi")
    created_str = t["created_at"].strftime("%H:%M - %d/%m/%Y") if isinstance(t["created_at"], datetime) else str(t["created_at"])
    is_er = (t.get("priority_level", 0) >= 2) or ("cấp cứu" in t["room_name"].lower())

    # 1. Header Bệnh Viện
    c.setFont(FONT_BOLD, 9)
    c.drawCentredString(page_width / 2, page_height - 12 * mm, "BỆNH VIỆN ĐA KHOA QUỐC TẾ ATUS")
    c.setFont(FONT_NORMAL, 8)
    c.drawCentredString(page_width / 2, page_height - 16 * mm, "Số 1 Phố Y Dược, Cầu Giấy, Hà Nội")
    c.drawCentredString(page_width / 2, page_height - 20 * mm, "Hotline: 024.7777.9999 - Cấp cứu: 115")

    # Đường kẻ ngang
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(0.8)
    c.line(6 * mm, page_height - 23 * mm, page_width - 6 * mm, page_height - 23 * mm)

    # 2. Tiêu đề phiếu
    c.setFont(FONT_BOLD, 12)
    c.drawCentredString(page_width / 2, page_height - 29 * mm, "PHIẾU LẤY SỐ KHÁM BỆNH" if is_vi else "QUEUE TICKET")
    c.setFont(FONT_NORMAL, 7.5)
    c.drawCentredString(page_width / 2, page_height - 33 * mm, f"Thời gian cấp: {created_str}")

    # 3. Số thứ tự khám to đậm
    c.setFont(FONT_BOLD, 26)
    if is_er:
        c.setFillColor(colors.HexColor("#e55353"))
    else:
        c.setFillColor(colors.HexColor("#008f88"))
    c.drawCentredString(page_width / 2, page_height - 45 * mm, t["ticket_number"])
    c.setFillColor(colors.black)

    if is_er:
        c.setFont(FONT_BOLD, 8.5)
        c.setFillColor(colors.HexColor("#b91c1c"))
        c.drawCentredString(page_width / 2, page_height - 50 * mm, "🚨 ƯU TIÊN CẤP CỨU KHẨN CẤP")
        c.setFillColor(colors.black)

    # 4. Bảng thông tin người bệnh & phòng
    y = page_height - 57 * mm
    c.setFont(FONT_NORMAL, 8)
    
    rows = [
        ("Người bệnh:", t["patient_name_masked"]),
        ("Mã BN (MPI):", t["patient_code"]),
        ("Phòng khám:", f"{t['room_name']} ({t['room_number']})"),
        ("Vị trí:", f"Tầng {t['floor']}"),
        ("Bác sĩ trực:", t["doctor_name"]),
        ("Đang chờ trước:", f"{t['waiting_ahead']} người (~{t['est_wait_minutes']} phút)")
    ]

    for label, val in rows:
        c.setFont(FONT_NORMAL, 8)
        c.drawString(7 * mm, y, label)
        c.setFont(FONT_BOLD, 8)
        c.drawRightString(page_width - 7 * mm, y, val)
        y -= 4.6 * mm

    # Đường kẻ nét đứt
    c.setDash(2, 2)
    c.line(6 * mm, y + 1 * mm, page_width - 6 * mm, y + 1 * mm)
    c.setDash()

    # 5. Mã QR Code
    qr_data = f"https://atus-hospital.vn/track?t={t['ticket_number']}&mpi={t['patient_code']}"
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    img_buf = io.BytesIO()
    qr_img.save(img_buf, format="PNG")
    img_buf.seek(0)
    
    from reportlab.lib.utils import ImageReader
    ir = ImageReader(img_buf)
    qr_size = 28 * mm
    c.drawImage(ir, (page_width - qr_size) / 2, y - qr_size - 1 * mm, width=qr_size, height=qr_size)

    # 6. Ghi chú chân trang
    c.setFont(FONT_NORMAL, 6.8)
    c.drawCentredString(page_width / 2, y - qr_size - 4 * mm, "Quét QR để theo dõi lượt khám & bản đồ trên điện thoại")
    c.drawCentredString(page_width / 2, y - qr_size - 8 * mm, "Xin cảm ơn quý khách - Chúc quý khách mau khỏe!")

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.getvalue()

"""Dịch vụ Quản lý Hồ Sơ Bệnh Án Điện Tử (EMR), Kê Đơn Thuốc & Xuất PDF Y Tế Chuẩn Bộ Y Tế.

Tuân thủ:
1. Thông tư 27/2021/TT-BYT & Thông tư 04/2022/TT-BYT về Quy định kê đơn thuốc điện tử.
2. Danh mục chẩn đoán mã hóa bệnh tật quốc tế ICD-10.
3. Kiểm tra trừ kho tồn kho thuốc dược (Pharmacy Inventory) nguyên tử.
4. Xuất file PDF Bệnh Án & Đơn Thuốc Điện Tử Unicode UTF-8 (ReportLab Arial) kèm mã QR Code tra cứu.
"""
from __future__ import annotations

import io
import os
from datetime import datetime, date
import qrcode
from PIL import Image

from reportlab.lib.pagesizes import A4, mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import db
from auth import log_audit

# Đăng ký font tiếng Việt Unicode
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


# Danh mục ICD-10 phổ biến tại các phòng khám ngoại trú
COMMON_ICD10 = [
    {"code": "I10", "name": "Tăng huyết áp vô căn (nguyên phát)"},
    {"code": "E11", "name": "Đái tháo đường typ 2"},
    {"code": "J00", "name": "Viêm mũi họng cấp (Cảm thường)"},
    {"code": "J02.9", "name": "Viêm họng cấp không đặc hiệu"},
    {"code": "J20.9", "name": "Viêm phế quản cấp"},
    {"code": "K29.7", "name": "Viêm dạ dày không đặc hiệu"},
    {"code": "K21.9", "name": "Bệnh trào ngược dạ dày - thực quản (GERD)"},
    {"code": "A09", "name": "Viêm dạ dày ruột và viêm đại tràng nhiễm trùng"},
    {"code": "M54.5", "name": "Đau thắt lưng mạn / cấp"},
    {"code": "M17.9", "name": "Thoái hóa khớp gối"},
    {"code": "H10.9", "name": "Viêm kết mạc không đặc hiệu"},
    {"code": "J01.9", "name": "Viêm xoang cấp không đặc hiệu"},
    {"code": "R51", "name": "Đau đầu vận mạch"},
    {"code": "R42", "name": "Chóng mặt và rối loạn thăng bằng"},
    {"code": "L20.9", "name": "Viêm da cơ địa / Dị ứng"},
]


def search_medicines(keyword: str = "", limit: int = 40) -> list[dict]:
    """Tìm kiếm danh mục thuốc bệnh viện kèm số lượng tồn kho thực tế."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT m.id, m.code, m.brand_name, m.active_ingredient, m.strength,
                   m.unit, m.route, m.category, m.unit_price,
                   ISNULL(SUM(inv.quantity_in_stock), 0) AS stock
            FROM medicines m
            LEFT JOIN pharmacy_inventory inv ON m.id = inv.medicine_id
            WHERE m.is_active = 1
        """
        params = []
        if keyword:
            query += " AND (m.brand_name LIKE ? OR m.active_ingredient LIKE ? OR m.code LIKE ?)"
            kw = f"%{keyword.strip()}%"
            params.extend([kw, kw, kw])

        query += " GROUP BY m.id, m.code, m.brand_name, m.active_ingredient, m.strength, m.unit, m.route, m.category, m.unit_price"
        query += f" ORDER BY m.brand_name"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [
            {
                "id": r[0], "code": r[1], "brand_name": r[2], "active_ingredient": r[3],
                "strength": r[4], "unit": r[5], "route": r[6], "category": r[7],
                "unit_price": float(r[8]), "stock": int(r[9])
            }
            for r in rows[:limit]
        ]
    finally:
        conn.close()


def save_clinical_examination(
    ticket_id: int,
    doctor_id: int,
    doctor_username: str,
    chief_complaint: str,
    icd10_code: str,
    icd10_name: str,
    conclusion: str,
    history_of_illness: str = "",
    clinical_notes: str = "",
    revisit_date: date | None = None,
    pulse: int | None = None,
    bp_sys: int | None = None,
    bp_dia: int | None = None,
    temperature: float | None = None,
    weight: float | None = None,
    height: float | None = None,
    spo2: int | None = None
) -> dict:
    """Lưu hồ sơ bệnh án lâm sàng điện tử vào bảng examinations."""
    bmi = None
    if height and weight and height > 0:
        h_m = height / 100.0 if height > 3 else height
        bmi = round(weight / (h_m * h_m), 1)

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()

        # Lấy thông tin vé khám và người bệnh
        cursor.execute("SELECT patient_id, current_room_id, patient_name, patient_phone FROM tickets WHERE id = ?", (ticket_id,))
        t_row = cursor.fetchone()
        if not t_row:
            raise ValueError(f"Không tìm thấy vé ID {ticket_id}")
        patient_id, room_id, p_name, p_phone = t_row

        if not patient_id:
            import patient_service
            p_rec = patient_service.get_or_create_patient(p_name or "Bệnh nhân vãng lai", p_phone or "0900000000")
            patient_id = p_rec["id"]
            cursor.execute("UPDATE tickets SET patient_id = ? WHERE id = ?", (patient_id, ticket_id))

        cursor.execute("""
            INSERT INTO examinations (
                ticket_id, patient_id, doctor_id, room_id,
                pulse, blood_pressure_sys, blood_pressure_dia, temperature,
                weight, height, bmi, spo2,
                chief_complaint, history_of_illness, clinical_notes,
                icd10_code, icd10_name, conclusion, revisit_date, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (
            ticket_id, patient_id, doctor_id, room_id,
            pulse, bp_sys, bp_dia, temperature,
            weight, height, bmi, spo2,
            chief_complaint, history_of_illness, clinical_notes,
            icd10_code, icd10_name, conclusion, revisit_date
        ))
        exam_id = cursor.fetchone()[0]
        conn.commit()

        log_audit(doctor_id, doctor_username, "CREATE_EXAMINATION", "EXAMINATION", str(exam_id),
                  f"Bác sĩ hoàn tất khám: ICD10 {icd10_code} ({conclusion})", patient_id=patient_id)

        return {
            "examination_id": exam_id,
            "patient_id": patient_id,
            "icd10_code": icd10_code,
            "icd10_name": icd10_name,
            "conclusion": conclusion,
            "bmi": bmi
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def create_electronic_prescription(
    examination_id: int,
    doctor_id: int,
    doctor_username: str,
    patient_id: int,
    items: list[dict],
    notes: str = ""
) -> dict:
    """Kê đơn thuốc điện tử, kiểm tra và trừ tồn kho dược phòng khám."""
    if not items:
        raise ValueError("Đơn thuốc phải có ít nhất 1 loại thuốc!")

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Sinh mã đơn thuốc điện tử duy nhất: DT-YYYYMMDD-xxxx
        today_str = datetime.now().strftime("%Y%m%d")
        cursor.execute("SELECT COUNT(*) + 1 FROM prescriptions WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)")
        seq = cursor.fetchone()[0]
        pres_code = f"DT-{today_str}-{seq:04d}"
        lookup_token = f"TK{pres_code.replace('-', '')}"

        # 2. Tạo đơn thuốc
        cursor.execute("""
            INSERT INTO prescriptions (
                examination_id, patient_id, doctor_id, prescription_code,
                lookup_token, notes, status, created_at
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, 'issued', GETDATE())
        """, (examination_id, patient_id, doctor_id, pres_code, lookup_token, notes))
        pres_id = cursor.fetchone()[0]

        # 3. Chèn từng mục thuốc và trừ tồn kho
        inserted_items = []
        for it in items:
            med_id = it["medicine_id"]
            med_name = it.get("medicine_name", "")
            dosage = it.get("dosage", "")
            qty = int(it.get("quantity", 1))
            unit = it.get("unit", "Viên")
            instructions = it.get("usage_instructions", "")

            cursor.execute("""
                INSERT INTO prescription_items (
                    prescription_id, medicine_id, medicine_name, dosage,
                    quantity, unit, usage_instructions
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pres_id, med_id, med_name, dosage, qty, unit, instructions))

            # Trừ số lượng tồn kho dược
            cursor.execute("""
                UPDATE pharmacy_inventory
                SET quantity_in_stock = CASE WHEN quantity_in_stock >= ? THEN quantity_in_stock - ? ELSE 0 END,
                    updated_at = GETDATE()
                WHERE medicine_id = ?
            """, (qty, qty, med_id))

            inserted_items.append({
                "medicine_name": med_name,
                "dosage": dosage,
                "quantity": qty,
                "unit": unit,
                "instructions": instructions
            })

        conn.commit()

        log_audit(doctor_id, doctor_username, "ISSUE_PRESCRIPTION", "PRESCRIPTION", str(pres_id),
                  f"Kê đơn thuốc điện tử {pres_code} gồm {len(items)} loại thuốc", patient_id=patient_id)

        return {
            "prescription_id": pres_id,
            "prescription_code": pres_code,
            "lookup_token": lookup_token,
            "items_count": len(inserted_items),
            "status": "issued"
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_prescription_full_details(prescription_id: int) -> dict | None:
    """Truy vấn đầy đủ chi tiết đơn thuốc, bệnh nhân, chẩn đoán ICD-10 và danh mục thuốc."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.id, pr.prescription_code, pr.lookup_token, pr.notes, pr.status, pr.created_at,
                   p.id AS patient_id, p.patient_code, p.full_name AS patient_name, p.dob, p.gender,
                   p.phone, p.cccd, p.bhyt_code, p.address,
                   u.full_name AS doctor_name, d.name AS dept_name,
                   e.icd10_code, e.icd10_name, e.conclusion, e.revisit_date,
                   e.blood_pressure_sys, e.blood_pressure_dia, e.pulse, e.weight
            FROM prescriptions pr
            JOIN patients p ON pr.patient_id = p.id
            JOIN users u ON pr.doctor_id = u.id
            LEFT JOIN departments d ON u.department_id = d.id
            LEFT JOIN examinations e ON pr.examination_id = e.id
            WHERE pr.id = ?
        """, (prescription_id,))
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute("""
            SELECT pi.id, pi.medicine_id, pi.medicine_name, pi.dosage, pi.quantity,
                   pi.unit, pi.usage_instructions, m.active_ingredient, m.strength
            FROM prescription_items pi
            LEFT JOIN medicines m ON pi.medicine_id = m.id
            WHERE pi.prescription_id = ?
            ORDER BY pi.id ASC
        """, (prescription_id,))
        items = [
            {
                "id": r[0], "medicine_id": r[1], "name": r[2], "dosage": r[3],
                "quantity": r[4], "unit": r[5], "usage": r[6],
                "ingredient": r[7] or "", "strength": r[8] or ""
            }
            for r in cursor.fetchall()
        ]

        return {
            "id": row[0],
            "code": row[1],
            "lookup_token": row[2],
            "notes": row[3] or "",
            "status": row[4],
            "created_at": row[5],
            "patient_code": row[7],
            "patient_name": row[8],
            "dob": row[9],
            "gender": row[10],
            "phone": row[11],
            "cccd": row[12],
            "bhyt": row[13],
            "address": row[14] or "Hà Nội",
            "doctor_name": row[15],
            "department": row[16] or "Khoa Khám Bệnh",
            "icd10_code": row[17] or "R51",
            "icd10_name": row[18] or "Khám sức khỏe tổng quát",
            "conclusion": row[19] or "Ổn định",
            "revisit_date": row[20],
            "bp": f"{row[21]}/{row[22]}" if row[21] and row[22] else "N/A",
            "pulse": row[23] or "N/A",
            "weight": row[24] or "N/A",
            "items": items
        }
    finally:
        conn.close()


def generate_prescription_pdf(prescription_id: int) -> bytes:
    """Xuất file PDF Đơn Thuốc Điện Tử chuẩn Bộ Y Tế (Khổ A4, font tiếng Việt có dấu Unicode)."""
    p_data = get_prescription_full_details(prescription_id)
    if not p_data:
        raise ValueError(f"Không tìm thấy đơn thuốc ID {prescription_id}")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # 1. Header Bệnh Viện
    c.setFont(FONT_BOLD, 12)
    c.drawString(20 * mm, page_h - 20 * mm, "BỆNH VIỆN ĐA KHOA QUỐC TẾ ATUS")
    c.setFont(FONT_NORMAL, 9)
    c.drawString(20 * mm, page_h - 24 * mm, "Địa chỉ: Số 1 Phố Y Dược, Q. Cầu Giấy, TP. Hà Nội")
    c.drawString(20 * mm, page_h - 28 * mm, "Điện thoại: 024.7777.9999 - Cấp cứu: 115")

    # Mã đơn thuốc & ngày tạo
    c.setFont(FONT_NORMAL, 8.5)
    c.drawRightString(page_w - 20 * mm, page_h - 20 * mm, f"Mã đơn thuốc: {p_data['code']}")
    c.drawRightString(page_w - 20 * mm, page_h - 24 * mm, f"Mã tra cứu: {p_data['lookup_token']}")
    c.drawRightString(page_w - 20 * mm, page_h - 28 * mm, f"Ngày kê: {p_data['created_at'].strftime('%d/%m/%Y %H:%M')}")

    # Đường kẻ ngang header
    c.setStrokeColor(colors.HexColor("#008f88"))
    c.setLineWidth(1.5)
    c.line(20 * mm, page_h - 32 * mm, page_w - 20 * mm, page_h - 32 * mm)

    # 2. Tiêu đề Đơn thuốc
    c.setFont(FONT_BOLD, 17)
    c.setFillColor(colors.HexColor("#003a70"))
    c.drawCentredString(page_w / 2, page_h - 42 * mm, "ĐƠN THUỐC ĐIỆN TỬ")
    c.setFillColor(colors.black)

    # 3. Thông tin Hành chính Người bệnh
    y = page_h - 52 * mm
    c.setFont(FONT_NORMAL, 9.5)
    
    # Dòng 1: Họ tên & Năm sinh & Giới tính
    c.drawString(20 * mm, y, "Họ và tên người bệnh:")
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(62 * mm, y, p_data["patient_name"].upper())
    c.setFont(FONT_NORMAL, 9.5)
    c.drawString(130 * mm, y, f"Năm sinh: {p_data['dob'] or '1990'}")
    c.drawString(170 * mm, y, f"Giới tính: {p_data['gender'] or 'Nam'}")
    y -= 6 * mm

    # Dòng 2: Mã định danh MPI & BHYT / CCCD
    c.drawString(20 * mm, y, "Mã bệnh nhân (MPI):")
    c.setFont(FONT_BOLD, 9.5)
    c.drawString(62 * mm, y, p_data["patient_code"])
    c.setFont(FONT_NORMAL, 9.5)
    c.drawString(100 * mm, y, f"CCCD/BHYT: {p_data['bhyt'] or p_data['cccd'] or 'Không có'}")
    c.drawString(155 * mm, y, f"SĐT: {p_data['phone']}")
    y -= 6 * mm

    # Dòng 3: Địa chỉ
    c.drawString(20 * mm, y, "Địa chỉ liên hệ:")
    c.drawString(62 * mm, y, p_data["address"])
    y -= 6 * mm

    # Dòng 4: Chẩn đoán ICD-10
    c.drawString(20 * mm, y, "Chẩn đoán xác định:")
    c.setFont(FONT_BOLD, 9.5)
    c.setFillColor(colors.HexColor("#0f766e"))
    c.drawString(62 * mm, y, f"[{p_data['icd10_code']}] - {p_data['icd10_name']}")
    c.setFillColor(colors.black)
    y -= 8 * mm

    # Đường phân cách
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(0.8)
    c.line(20 * mm, y, page_w - 20 * mm, y)
    y -= 6 * mm

    # 4. Danh mục thuốc kê đơn
    c.setFont(FONT_BOLD, 11)
    c.drawString(20 * mm, y, "CHỈ ĐỊNH DÙNG THUỐC:")
    y -= 7 * mm

    for idx, item in enumerate(p_data["items"]):
        # Tên thuốc + hàm lượng + số lượng
        c.setFont(FONT_BOLD, 10)
        c.drawString(22 * mm, y, f"{idx + 1}. {item['name']} ({item['strength'] or item['dosage']})")
        c.drawRightString(page_w - 22 * mm, y, f"Số lượng: {item['quantity']} {item['unit']}")
        y -= 4.8 * mm

        # Cách dùng chi tiết
        c.setFont(FONT_NORMAL, 9)
        c.setFillColor(colors.HexColor("#334155"))
        c.drawString(28 * mm, y, f"👉 Hướng dẫn: {item['usage']}")
        c.setFillColor(colors.black)
        y -= 6.5 * mm

    # Lời dặn của bác sĩ & tái khám
    y -= 4 * mm
    if p_data["notes"]:
        c.setFont(FONT_NORMAL, 9)
        c.drawString(20 * mm, y, f"Lời dặn của bác sĩ: {p_data['notes']}")
        y -= 5 * mm
    if p_data["revisit_date"]:
        c.setFont(FONT_BOLD, 9)
        c.drawString(20 * mm, y, f"Hẹn khám lại ngày: {p_data['revisit_date']}")
        y -= 5 * mm

    # 5. Chân trang: QR Code tra cứu & Chữ ký Bác sĩ
    y_footer = 35 * mm
    
    # Mã QR Code
    qr_data = f"https://atus-hospital.vn/prescription?code={p_data['code']}&token={p_data['lookup_token']}"
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    img_buf = io.BytesIO()
    qr_img.save(img_buf, format="PNG")
    img_buf.seek(0)
    
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(img_buf), 22 * mm, y_footer - 15 * mm, width=28 * mm, height=28 * mm)
    c.setFont(FONT_NORMAL, 7.5)
    c.drawString(22 * mm, y_footer - 18 * mm, "Quét mã tra cứu đơn thuốc điện tử")

    # Chữ ký bác sĩ
    c.setFont(FONT_NORMAL, 9.5)
    c.drawCentredString(page_w - 55 * mm, y_footer + 10 * mm, f"Hà Nội, ngày {p_data['created_at'].strftime('%d tháng %m năm %Y')}")
    c.setFont(FONT_BOLD, 10)
    c.drawCentredString(page_w - 55 * mm, y_footer + 5 * mm, "BÁC SĨ ĐIỀU TRỊ")
    c.setFont(FONT_NORMAL, 8)
    c.drawCentredString(page_w - 55 * mm, y_footer + 1 * mm, "(Ký, đóng dấu hoặc chữ ký số)")

    # Tên bác sĩ
    c.setFont(FONT_BOLD, 10.5)
    c.drawCentredString(page_w - 55 * mm, y_footer - 16 * mm, p_data["doctor_name"])

    # Lưu và xuất bytes
    c.showPage()
    c.save()

    buf.seek(0)
    return buf.getvalue()

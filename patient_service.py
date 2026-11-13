"""Dịch vụ Quản lý Hồ sơ Người bệnh Định danh (Patient Master Index - MPI).

Tuân thủ Nghị định 13/2023/NĐ-CP về Bảo vệ dữ liệu cá nhân y tế:
1. Nhận diện người bệnh qua khóa ưu tiên: [CCCD / Mã Định Danh] > [Mã thẻ BHYT] > [Số điện thoại].
2. Tự động sinh mã định danh duy nhất (Patient Master ID): AT-xxxxxx.
3. Xử lý gộp hồ sơ trùng lặp (Patient Deduplication & Merge) an toàn, giữ nguyên toàn bộ lịch sử khám, xét nghiệm và đơn thuốc.
"""
from __future__ import annotations

import re
from datetime import datetime, date
import db
from auth import log_audit


def normalize_phone(phone: str) -> str:
    """Chuẩn hóa số điện thoại về định dạng 10 chữ số."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits


def generate_patient_code(cursor) -> str:
    """Sinh mã định danh người bệnh (Patient Master Code): AT-xxxxxx (6 chữ số tăng dần)."""
    cursor.execute("SELECT ISNULL(MAX(id), 0) + 1 FROM patients")
    next_id = cursor.fetchone()[0]
    return f"AT-{next_id:06d}"


def get_or_create_patient(
    full_name: str,
    phone: str,
    cccd: str | None = None,
    bhyt_code: str | None = None,
    dob: str | date | None = None,
    gender: str | None = None,
    address: str | None = None,
    allergies: str | None = None
) -> dict:
    """Tìm kiếm hoặc đăng ký hồ sơ bệnh nhân mới theo khóa định danh CCCD/BHYT/SĐT.
    
    Quy tắc nhận diện:
    1. Tìm theo CCCD (chính xác tuyệt đối).
    2. Tìm theo Mã thẻ BHYT.
    3. Tìm theo Số điện thoại và Họ tên.
    4. Nếu hồ sơ đã từng bị gộp (merged_into_id), tự động chuyển tiếp tới hồ sơ chủ mới nhất.
    """
    clean_name = full_name.strip()
    clean_phone = normalize_phone(phone)
    clean_cccd = cccd.strip() if cccd and cccd.strip() else None
    clean_bhyt = bhyt_code.strip().upper() if bhyt_code and bhyt_code.strip() else None

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()

        found_id = None

        # 1. Tra cứu theo CCCD
        if clean_cccd:
            cursor.execute("SELECT id, merged_into_id FROM patients WHERE cccd = ?", (clean_cccd,))
            row = cursor.fetchone()
            if row:
                found_id = row[1] if row[1] else row[0]

        # 2. Tra cứu theo Mã thẻ BHYT
        if not found_id and clean_bhyt:
            cursor.execute("SELECT id, merged_into_id FROM patients WHERE bhyt_code = ?", (clean_bhyt,))
            row = cursor.fetchone()
            if row:
                found_id = row[1] if row[1] else row[0]

        # 3. Tra cứu theo Số điện thoại và Họ tên
        if not found_id and clean_phone:
            cursor.execute("""
                SELECT id, merged_into_id 
                FROM patients 
                WHERE phone = ? AND LOWER(full_name) = LOWER(?)
            """, (clean_phone, clean_name))
            row = cursor.fetchone()
            if row:
                found_id = row[1] if row[1] else row[0]

        # ── NẾU TÌM THẤY BỆNH NHÂN CŨ: CẬP NHẬT THÔNG TIN BỔ SUNG ──
        if found_id:
            cursor.execute("""
                UPDATE patients
                SET cccd = COALESCE(cccd, ?),
                    bhyt_code = COALESCE(bhyt_code, ?),
                    dob = COALESCE(dob, ?),
                    gender = COALESCE(gender, ?),
                    address = COALESCE(address, ?),
                    allergies = COALESCE(allergies, ?),
                    updated_at = GETDATE()
                WHERE id = ?
            """, (clean_cccd, clean_bhyt, dob, gender, address, allergies, found_id))
            conn.commit()

            cursor.execute("""
                SELECT id, patient_code, full_name, phone, cccd, bhyt_code, dob, gender, address, allergies
                FROM patients WHERE id = ?
            """, (found_id,))
            p = cursor.fetchone()
            return {
                "id": p[0], "patient_code": p[1], "full_name": p[2], "phone": p[3],
                "cccd": p[4] or "", "bhyt_code": p[5] or "", "dob": str(p[6]) if p[6] else "",
                "gender": p[7] or "", "address": p[8] or "", "allergies": p[9] or "",
                "is_new": False
            }

        # ── NẾU LÀ BỆNH NHÂN MỚI: TẠO HỒ SƠ MASTER MỚI ──
        patient_code = generate_patient_code(cursor)
        cursor.execute("""
            INSERT INTO patients (patient_code, full_name, phone, cccd, bhyt_code, dob, gender, address, allergies, is_active, created_at, updated_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE(), GETDATE())
        """, (patient_code, clean_name, clean_phone, clean_cccd, clean_bhyt, dob, gender, address, allergies))
        new_id = cursor.fetchone()[0]
        conn.commit()

        log_audit(None, "KIOSK", "CREATE_PATIENT", "PATIENT", str(new_id), f"Đăng ký bệnh nhân mới {patient_code} ({clean_name})", patient_id=new_id)

        return {
            "id": new_id,
            "patient_code": patient_code,
            "full_name": clean_name,
            "phone": clean_phone,
            "cccd": clean_cccd or "",
            "bhyt_code": clean_bhyt or "",
            "dob": str(dob) if dob else "",
            "gender": gender or "",
            "address": address or "",
            "allergies": allergies or "",
            "is_new": True
        }
    finally:
        conn.close()


def merge_patient_records(source_patient_id: int, target_patient_id: int, reason: str, merged_by_user_id: int | None = None) -> bool:
    """Gộp hồ sơ trùng lặp (Merge Records):
    
    1. Chuyển toàn bộ vé khám (tickets), hồ sơ khám (examinations) và đơn thuốc (prescriptions) sang target_patient_id.
    2. Đánh dấu source_patient_id thành inactive và trỏ merged_into_id = target_patient_id.
    3. Ghi lại lịch sử gộp vào bảng patient_merges và nhật ký kiểm toán.
    """
    if source_patient_id == target_patient_id:
        raise ValueError("Không thể gộp hồ sơ vào chính nó.")

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()

        # 1. Chuyển vé khám
        cursor.execute("UPDATE tickets SET patient_id = ? WHERE patient_id = ?", (target_patient_id, source_patient_id))

        # 2. Chuyển hồ sơ khám bệnh án
        cursor.execute("UPDATE examinations SET patient_id = ? WHERE patient_id = ?", (target_patient_id, source_patient_id))

        # 3. Chuyển đơn thuốc
        cursor.execute("UPDATE prescriptions SET patient_id = ? WHERE patient_id = ?", (target_patient_id, source_patient_id))

        # 4. Đánh dấu hồ sơ nguồn đã gộp
        cursor.execute("""
            UPDATE patients
            SET is_active = 0, merged_into_id = ?, updated_at = GETDATE()
            WHERE id = ?
        """, (target_patient_id, source_patient_id))

        # 5. Ghi lịch sử gộp
        cursor.execute("""
            INSERT INTO patient_merges (source_patient_id, target_patient_id, reason, merged_by_user_id, merged_at)
            VALUES (?, ?, ?, ?, GETDATE())
        """, (source_patient_id, target_patient_id, reason, merged_by_user_id))

        conn.commit()

        log_audit(merged_by_user_id, "STAFF", "MERGE_PATIENTS", "PATIENT", str(target_patient_id),
                  f"Gộp hồ sơ BN #{source_patient_id} vào BN #{target_patient_id}. Lý do: {reason}",
                  patient_id=target_patient_id)
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def search_patients(query: str, limit: int = 20) -> list[dict]:
    """Tìm kiếm hồ sơ bệnh nhân theo Họ tên, SĐT, CCCD hoặc Mã BHYT."""
    q = query.strip()
    if not q:
        return []

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        search_term = f"%{q}%"
        cursor.execute(f"""
            SELECT TOP ({limit}) id, patient_code, full_name, phone, cccd, bhyt_code, dob, gender, address, allergies, is_active
            FROM patients
            WHERE is_active = 1 AND (
                full_name LIKE ? OR phone LIKE ? OR cccd LIKE ? OR bhyt_code LIKE ? OR patient_code LIKE ?
            )
            ORDER BY id DESC
        """, (search_term, search_term, search_term, search_term, search_term))
        rows = cursor.fetchall()
        return [
            {
                "id": r[0], "patient_code": r[1], "full_name": r[2], "phone": r[3],
                "cccd": r[4] or "", "bhyt_code": r[5] or "", "dob": str(r[6]) if r[6] else "",
                "gender": r[7] or "", "address": r[8] or "", "allergies": r[9] or ""
            }
            for r in rows
        ]
    finally:
        conn.close()

"""Service quản lý cấp số hàng đợi nguyên tử, luân chuyển bệnh nhân lâm sàng & cận lâm sàng.

Tuân thủ an toàn y tế và kiến trúc phân luồng bệnh viện:
1. Chống Race Condition tuyệt đối: Bảng bộ đếm room_daily_counters cập nhật nguyên tử bằng UPDATE ... OUTPUT.
2. Ràng buộc cứng: UNIQUE (current_room_id, visit_date, daily_seq).
3. Chuẩn hóa múi giờ Việt Nam: Asia/Ho_Chi_Minh (UTC+7) cho mọi tính toán ngày và ca khám.
4. Tích hợp Patient Master Index (MPI): Tự động liên kết mã bệnh nhân duy nhất AT-xxxxxx.
5. Kiểm tra ca trực bác sĩ: Chỉ cấp số vào các phòng có ca trực hoạt động (ngoại trừ Khoa Cấp Cứu T1-04 mở 24/7).
"""
from __future__ import annotations

from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import db
from auth import log_audit
import patient_service

# Múi giờ chuẩn Việt Nam (UTC+7)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def get_vn_now() -> datetime:
    """Lấy thời gian hiện tại theo múi giờ Việt Nam (UTC+7)."""
    return datetime.now(VN_TZ)


def get_vn_today() -> date:
    """Lấy ngày hiện tại theo múi giờ Việt Nam (UTC+7)."""
    return get_vn_now().date()


def get_current_shift(check_time: time | None = None) -> str:
    """Xác định ca làm việc hiện tại: 'morning', 'afternoon' hoặc 'night'."""
    t = check_time or get_vn_now().time()
    if time(7, 0) <= t < time(12, 0):
        return "morning"
    elif time(12, 0) <= t < time(18, 0):
        return "afternoon"
    else:
        return "night"


def get_all_rooms(room_type: str | None = None, include_restricted: bool = False) -> list[dict]:
    """Lấy danh sách các phòng/khu vực chức năng trong bệnh viện."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT r.id, r.code, r.name, r.name_en, r.room_number, r.floor, r.type, r.prefix, 
                   r.department_id, d.name as department_name, r.instructions, r.instructions_en,
                   r.is_restricted, r.is_active
            FROM rooms r
            LEFT JOIN departments d ON r.department_id = d.id
            WHERE r.is_active = 1
        """
        params = []
        if not include_restricted:
            query += " AND (r.is_restricted = 0 OR r.is_restricted IS NULL)"
        if room_type:
            query += " AND r.type = ?"
            params.append(room_type)
        query += " ORDER BY r.floor, r.code"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            {
                "id": r[0], "code": r[1], "name": r[2], "name_en": r[3] or "",
                "room_number": r[4], "floor": r[5], "type": r[6], "prefix": r[7],
                "department_id": r[8], "department_name": r[9] or "",
                "instructions": r[10] or "", "instructions_en": r[11] or "",
                "is_restricted": bool(r[12]), "is_active": bool(r[13])
            }
            for r in rows
        ]
    finally:
        conn.close()


def check_room_shift_available(room_id: int, target_date: date | None = None) -> dict:
    """Kiểm tra xem phòng khám có ca trực hoạt động hay không.
    
    Quy tắc nghiệp vụ:
    - Khoa Cấp Cứu (T1-04) luôn mở 24/7.
    - Các phòng khám ngoại trú yêu cầu có lịch trực của bác sĩ trong ca hiện tại.
    """
    check_d = target_date or get_vn_today()
    current_shift = get_current_shift()

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, type FROM rooms WHERE id = ?", (room_id,))
        room = cursor.fetchone()
        if not room:
            return {"available": False, "reason": "Phòng không tồn tại", "doctor": None, "schedule_id": None}

        rcode, rname, rtype = room

        # Khoa Cấp Cứu T1-04 luôn mở 24/7
        if rcode == "T1-04" or rtype == "emergency":
            return {"available": True, "reason": "Cấp cứu 24/7 sẵn sàng", "doctor": "Bác sĩ trực Cấp cứu", "schedule_id": None}

        # Tra cứu ca trực của bác sĩ
        cursor.execute("""
            SELECT s.id, s.doctor_id, u.full_name as doctor_name, s.shift, s.start_time, s.end_time
            FROM doctor_schedules s
            JOIN users u ON s.doctor_id = u.id
            WHERE s.room_id = ? AND s.work_date = ? AND s.is_active = 1
              AND (s.shift = ? OR s.shift = 'full_day')
        """, (room_id, check_d, current_shift))
        row = cursor.fetchone()

        if row:
            return {
                "available": True,
                "reason": "Phòng có bác sĩ đang trực",
                "schedule_id": row[0],
                "doctor_id": row[1],
                "doctor_name": row[2],
                "shift": row[3]
            }

        # Nếu không có ca đúng shift, kiểm tra xem hôm nay có bất kỳ ca nào không
        cursor.execute("""
            SELECT s.id, u.full_name as doctor_name, s.shift 
            FROM doctor_schedules s
            JOIN users u ON s.doctor_id = u.id
            WHERE s.room_id = ? AND s.work_date = ? AND s.is_active = 1
        """, (room_id, check_d))
        any_shift = cursor.fetchone()
        if any_shift:
            return {
                "available": True,  # Cho phép đặt lịch trước cho ca khác trong ngày
                "reason": f"Bác sĩ {any_shift[1]} (Ca {any_shift[2]})",
                "schedule_id": any_shift[0],
                "doctor_name": any_shift[1],
                "shift": any_shift[2]
            }

        return {
            "available": False,
            "reason": f"Hiện không có bác sĩ trực ca {current_shift} tại phòng {rname}.",
            "doctor": None,
            "schedule_id": None
        }
    finally:
        conn.close()


def issue_ticket(
    room_id: int,
    patient_name: str,
    patient_phone: str,
    cccd: str | None = None,
    bhyt_code: str | None = None,
    patient_notes: str = "",
    priority_level: int = 0,
    force_emergency: bool = False
) -> dict:
    """Cấp số thứ tự hàng đợi MỚI theo cơ chế NGUYÊN TỬ (Atomic Counter) và Múi giờ Việt Nam.
    
    Quy tắc an toàn chống Race Condition:
    1. Chuẩn hóa ngày khám theo múi giờ Asia/Ho_Chi_Minh.
    2. Cập nhật số thứ tự tăng nguyên tử trên bảng room_daily_counters bằng UPDATE ... OUTPUT.
    3. Đăng ký hoặc liên kết Patient Master Index (MPI).
    4. Ghi nhận vé vào bảng tickets với UNIQUE constraint bảo vệ.
    """
    today_vn = get_vn_today()
    clean_name = patient_name.strip()
    clean_phone = patient_phone.strip()

    # 1. Liên kết Patient Master Index
    patient_record = patient_service.get_or_create_patient(
        full_name=clean_name,
        phone=clean_phone,
        cccd=cccd,
        bhyt_code=bhyt_code
    )
    patient_id = patient_record["id"]
    patient_code = patient_record["patient_code"]

    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()

        # 2. Lấy thông tin phòng khám
        cursor.execute("SELECT id, code, name, room_number, floor, prefix, instructions, type FROM rooms WHERE id = ?", (room_id,))
        room = cursor.fetchone()
        if not room:
            raise ValueError(f"Không tìm thấy phòng với ID {room_id}")

        rid, rcode, rname, rnumber, floor, prefix, instructions, rtype = room

        # 3. Kiểm tra ca trực bác sĩ (trừ khi là cấp cứu khẩn cấp)
        schedule_id = None
        is_emergency = force_emergency or (rcode == "T1-04") or (rtype == "emergency") or (priority_level >= 2)
        if not is_emergency:
            shift_info = check_room_shift_available(room_id, today_vn)
            schedule_id = shift_info.get("schedule_id")

        # 4. TĂNG SỐ THỨ TỰ NGUYÊN TỬ TRÊN BẢNG room_daily_counters
        # Sử dụng MERGE an toàn đảm bảo luôn có bản ghi cho cặp (room_id, today_vn)
        cursor.execute("""
            MERGE room_daily_counters WITH (HOLDLOCK) AS target
            USING (SELECT ? AS room_id, ? AS visit_date) AS source
            ON (target.room_id = source.room_id AND target.visit_date = source.visit_date)
            WHEN NOT MATCHED THEN
                INSERT (room_id, visit_date, current_seq, updated_at)
                VALUES (source.room_id, source.visit_date, 0, GETDATE());
        """, (room_id, today_vn))

        # Atomic increment với OUTPUT
        cursor.execute("""
            UPDATE room_daily_counters
            SET current_seq = current_seq + 1, updated_at = GETDATE()
            OUTPUT INSERTED.current_seq
            WHERE room_id = ? AND visit_date = ?;
        """, (room_id, today_vn))
        next_seq = cursor.fetchone()[0]

        ticket_code = f"{prefix}-{next_seq:03d}"
        ticket_status = "emergency_override" if is_emergency else "waiting"
        effective_priority = 2 if is_emergency else priority_level

        # 5. Chèn vé mới vào bảng tickets
        cursor.execute("""
            INSERT INTO tickets (ticket_number, daily_seq, patient_id, patient_name, patient_phone, patient_notes,
                                 initial_room_id, current_room_id, schedule_id, status, priority_level, visit_date, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (ticket_code, next_seq, patient_id, clean_name, clean_phone, patient_notes,
              room_id, room_id, schedule_id, ticket_status, effective_priority, today_vn))
        ticket_id = cursor.fetchone()[0]

        # 6. Đếm số người đang chờ trước người này
        cursor.execute("""
            SELECT COUNT(*) 
            FROM tickets 
            WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic')
              AND (priority_level > ? OR (priority_level = ? AND id < ?))
        """, (room_id, today_vn, effective_priority, effective_priority, ticket_id))
        waiting_ahead = cursor.fetchone()[0]

        conn.commit()

        # Rút gọn tên cho hiển thị vé Kiosk (Nghị định 13)
        parts = clean_name.split()
        if len(parts) >= 3:
            shortened_name = f"{parts[0]} {' '.join(p[0] + '.' for p in parts[1:-1])} {parts[-1]}"
        elif len(parts) == 2:
            shortened_name = f"{parts[0]} {parts[1][0]}."
        else:
            shortened_name = clean_name

        log_audit(None, "KIOSK", "ISSUE_TICKET", "TICKET", str(ticket_id),
                  f"Cấp vé {ticket_code} ({patient_code}) tại phòng {rname}", patient_id=patient_id)

        return {
            "ticket_id": ticket_id,
            "ticket_number": ticket_code,
            "daily_seq": next_seq,
            "patient_id": patient_id,
            "patient_code": patient_code,
            "patient_name": clean_name,
            "patient_short_name": shortened_name,
            "patient_phone": clean_phone,
            "room_id": room_id,
            "room_code": rcode,
            "room_name": rname,
            "room_number": rnumber,
            "floor": floor,
            "instructions": instructions or "",
            "waiting_ahead": waiting_ahead,
            "priority_level": effective_priority,
            "status": ticket_status,
            "is_emergency": is_emergency,
            "created_at": get_vn_now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_room_queue(room_id: int) -> dict:
    """Lấy danh sách hàng đợi thời gian thực của một phòng khám."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today_vn = get_vn_today()

        cursor.execute("""
            SELECT t.id, t.ticket_number, t.daily_seq, t.patient_name, t.patient_phone, t.patient_notes,
                   t.initial_room_id, t.current_room_id, t.status, t.priority_level, t.created_at, t.called_at,
                   r_init.name as initial_room_name, r_init.room_number as initial_room_number,
                   p.patient_code, p.allergies
            FROM tickets t
            LEFT JOIN rooms r_init ON t.initial_room_id = r_init.id
            LEFT JOIN patients p ON t.patient_id = p.id
            WHERE t.current_room_id = ? AND t.visit_date = ? AND t.status NOT IN ('completed', 'skipped')
            ORDER BY 
                CASE 
                    WHEN t.status = 'calling' THEN 1
                    WHEN t.status = 'in_progress' THEN 2
                    WHEN t.status = 'cls_in_progress' THEN 2
                    WHEN t.status = 'returned_to_clinic' THEN 3
                    WHEN t.status = 'emergency_override' THEN 3
                    WHEN t.status = 'waiting' THEN 4
                    ELSE 5
                END,
                t.priority_level DESC,
                t.id ASC
        """, (room_id, today_vn))
        rows = cursor.fetchall()

        calling = []
        in_progress = []
        waiting = []

        for r in rows:
            item = {
                "id": r[0], "ticket_number": r[1], "daily_seq": r[2],
                "patient_name": r[3], "patient_phone": r[4], "patient_notes": r[5] or "",
                "initial_room_id": r[6], "current_room_id": r[7], "status": r[8],
                "priority_level": r[9],
                "created_at": r[10].strftime("%H:%M") if r[10] else "",
                "called_at": r[11].strftime("%H:%M") if r[11] else "",
                "initial_room_name": r[12] or "",
                "initial_room_number": r[13] or "",
                "patient_code": r[14] or "",
                "allergies": r[15] or ""
            }
            if item["status"] == "calling":
                calling.append(item)
            elif item["status"] in ("in_progress", "cls_in_progress"):
                in_progress.append(item)
            else:
                waiting.append(item)

        return {
            "calling": calling,
            "in_progress": in_progress,
            "waiting": waiting,
            "total_waiting": len(waiting),
            "total_today": len(rows)
        }
    finally:
        conn.close()


def call_next_patient(room_id: int, user_id: int, username: str) -> dict | None:
    """Bác sĩ hoặc KTV bấm Gọi bệnh nhân tiếp theo trong hàng đợi."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today_vn = get_vn_today()

        cursor.execute("""
            SELECT TOP 1 id, ticket_number, patient_name, patient_phone
            FROM tickets
            WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic', 'emergency_override')
            ORDER BY 
                CASE 
                    WHEN status = 'emergency_override' THEN 1
                    WHEN status = 'returned_to_clinic' THEN 2 
                    ELSE 3 
                END,
                priority_level DESC,
                id ASC
        """, (room_id, today_vn))
        row = cursor.fetchone()
        if not row:
            return None

        ticket_id, ticket_num, p_name, p_phone = row

        cursor.execute("""
            UPDATE tickets
            SET status = 'calling', called_at = GETDATE()
            WHERE id = ?
        """, (ticket_id,))
        conn.commit()

        log_audit(user_id, username, "CALL_PATIENT", "TICKET", str(ticket_id), f"Gọi vé {ticket_num} ({p_name}) tại phòng {room_id}")

        return {
            "ticket_id": ticket_id,
            "ticket_number": ticket_num,
            "patient_name": p_name,
            "patient_phone": p_phone
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def start_exam(ticket_id: int, user_id: int, username: str) -> bool:
    """Xác nhận bệnh nhân đã vào phòng và bắt đầu khám / thực hiện xét nghiệm."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_room_id FROM tickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        if not row:
            return False

        cursor.execute("SELECT type FROM rooms WHERE id = ?", (row[0],))
        rtype = cursor.fetchone()[0]

        new_status = "cls_in_progress" if rtype == "paraclinical" else "in_progress"

        cursor.execute("""
            UPDATE tickets
            SET status = ?
            WHERE id = ?
        """, (new_status, ticket_id))
        conn.commit()
        log_audit(user_id, username, "START_EXAM", "TICKET", str(ticket_id), f"Bắt đầu khám trạng thái {new_status}")
        return True
    finally:
        conn.close()


def create_clinical_order(ticket_id: int, doctor_id: int, doctor_username: str, 
                          clinic_room_id: int, target_room_id: int, 
                          order_type: str, order_name: str, notes: str = "") -> dict:
    """Bác sĩ chỉ định cận lâm sàng (lấy máu, X-Quang, CT/MRI, siêu âm...)."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today_vn = get_vn_today()

        cursor.execute("SELECT name, room_number, floor, prefix, instructions FROM rooms WHERE id = ?", (target_room_id,))
        cls_room = cursor.fetchone()
        if not cls_room:
            raise ValueError(f"Không tìm thấy phòng cận lâm sàng ID {target_room_id}")

        cls_name, cls_number, cls_floor, cls_prefix, cls_inst = cls_room

        # Tăng số thứ tự phòng CLS qua bảng counter
        cursor.execute("""
            MERGE room_daily_counters WITH (HOLDLOCK) AS target
            USING (SELECT ? AS room_id, ? AS visit_date) AS source
            ON (target.room_id = source.room_id AND target.visit_date = source.visit_date)
            WHEN NOT MATCHED THEN
                INSERT (room_id, visit_date, current_seq, updated_at)
                VALUES (source.room_id, source.visit_date, 0, GETDATE());
        """, (target_room_id, today_vn))

        cursor.execute("""
            UPDATE room_daily_counters
            SET current_seq = current_seq + 1, updated_at = GETDATE()
            OUTPUT INSERTED.current_seq
            WHERE room_id = ? AND visit_date = ?;
        """, (target_room_id, today_vn))
        cls_seq = cursor.fetchone()[0]
        cls_ticket_number = f"{cls_prefix}-{cls_seq:03d}"

        # Lưu y lệnh
        cursor.execute("""
            INSERT INTO clinical_orders (ticket_id, doctor_id, clinic_room_id, target_room_id, 
                                        order_type, order_name, cls_ticket_number, notes, status, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', GETDATE())
        """, (ticket_id, doctor_id, clinic_room_id, target_room_id, order_type, order_name, cls_ticket_number, notes))
        order_id = cursor.fetchone()[0]

        # Cập nhật vé bệnh nhân: chuyển phòng hiện tại sang phòng CLS
        cursor.execute("""
            UPDATE tickets
            SET current_room_id = ?, status = 'waiting'
            WHERE id = ?
        """, (target_room_id, ticket_id))

        conn.commit()

        log_audit(doctor_id, doctor_username, "CREATE_CLS_ORDER", "ORDER", str(order_id),
                  f"Chỉ định {order_name} tại {cls_name} ({cls_ticket_number}) cho vé {ticket_id}")

        return {
            "order_id": order_id,
            "cls_ticket_number": cls_ticket_number,
            "target_room_name": cls_name,
            "target_room_number": cls_number,
            "target_floor": cls_floor,
            "instructions": cls_inst or "",
            "order_name": order_name
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def complete_cls_order(order_id: int, technician_id: int, technician_username: str, results: str = "") -> dict:
    """Kỹ thuật viên tại phòng CLS hoàn tất y lệnh và đưa bệnh nhân quay lại phòng khám ban đầu."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.id, o.ticket_id, o.clinic_room_id, o.order_name, t.ticket_number, t.patient_name,
                   r_clinic.name as clinic_name, r_clinic.room_number as clinic_number, r_clinic.floor as clinic_floor,
                   r_clinic.instructions as clinic_inst
            FROM clinical_orders o
            JOIN tickets t ON o.ticket_id = t.id
            JOIN rooms r_clinic ON o.clinic_room_id = r_clinic.id
            WHERE o.id = ?
        """, (order_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy chỉ định ID {order_id}")

        (oid, ticket_id, clinic_room_id, order_name, ticket_num, p_name,
         clinic_name, clinic_number, clinic_floor, clinic_inst) = row

        cursor.execute("""
            UPDATE clinical_orders
            SET status = 'completed', results = ?, completed_at = GETDATE()
            WHERE id = ?
        """, (results, order_id))

        cursor.execute("""
            UPDATE tickets
            SET current_room_id = initial_room_id,
                status = 'returned_to_clinic',
                priority_level = 1
            WHERE id = ?
        """, (ticket_id,))

        conn.commit()

        log_audit(technician_id, technician_username, "COMPLETE_CLS_ORDER", "ORDER", str(order_id),
                  f"KTV hoàn tất {order_name} cho vé {ticket_num}, chuyển về phòng {clinic_name}")

        return {
            "ticket_number": ticket_num,
            "patient_name": p_name,
            "return_clinic_name": clinic_name,
            "return_clinic_number": clinic_number,
            "return_floor": clinic_floor,
            "instructions": clinic_inst or ""
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def complete_ticket(ticket_id: int, user_id: int, username: str) -> bool:
    """Bác sĩ kết thúc lượt khám."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets
            SET status = 'completed', completed_at = GETDATE()
            WHERE id = ?
        """, (ticket_id,))
        conn.commit()
        log_audit(user_id, username, "COMPLETE_TICKET", "TICKET", str(ticket_id), "Hoàn thành lượt khám")
        return True
    finally:
        conn.close()


def recall_patient(ticket_id: int, user_id: int, username: str) -> dict | None:
    """Bác sĩ hoặc KTV bấm Gọi lại lần 2 cho bệnh nhân chưa kịp vào phòng."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.ticket_number, t.patient_name, t.patient_phone,
                   r.name, r.room_number, r.floor, t.priority_level
            FROM tickets t
            JOIN rooms r ON t.current_room_id = r.id
            WHERE t.id = ?
        """, (ticket_id,))
        row = cursor.fetchone()
        if not row:
            return None

        tid, tnum, pname, pphone, rname, rnum, floor, plvl = row
        cursor.execute("UPDATE tickets SET called_at = GETDATE(), status = 'calling' WHERE id = ?", (ticket_id,))
        conn.commit()

        log_audit(user_id, username, "RECALL_PATIENT", "TICKET", str(ticket_id), f"Gọi lại vé {tnum} ({pname}) tại phòng {rname}")

        return {
            "ticket_id": tid,
            "ticket_number": tnum,
            "patient_name": pname,
            "patient_phone": pphone,
            "room_name": rname,
            "room_number": rnum,
            "floor": floor,
            "is_emergency": (plvl >= 2)
        }
    finally:
        conn.close()


def get_callboard_data(floor: int | None = None) -> dict:
    """Truy vấn dữ liệu tổng hợp phục vụ hiển thị màn hình TV Callboard sảnh chờ."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today_vn = get_vn_today()

        # 1. Lượt gọi mới nhất gần đây (đang có status = 'calling')
        er_filter = ""
        er_params = [today_vn]
        if floor:
            er_filter = " AND r.floor = ?"
            er_params.append(floor)

        cursor.execute(f"""
            SELECT TOP 1 t.id, t.ticket_number, t.patient_name,
                   r.name AS room_name, r.room_number, r.floor,
                   t.called_at, t.priority_level,
                   u.full_name AS doctor_name
            FROM tickets t
            JOIN rooms r ON t.current_room_id = r.id
            LEFT JOIN doctor_schedules ds ON t.schedule_id = ds.id
            LEFT JOIN users u ON ds.doctor_id = u.id
            WHERE t.visit_date = ? AND t.status = 'calling' AND t.called_at IS NOT NULL {er_filter}
            ORDER BY t.called_at DESC
        """, er_params)
        latest_row = cursor.fetchone()

        latest_calling = None
        if latest_row:
            p_full = latest_row[2] or ""
            p_parts = p_full.split()
            masked_name = f"{p_parts[0]} {' '.join(p[0] + '.' for p in p_parts[1:-1])} {p_parts[-1]}" if len(p_parts) >= 3 else p_full

            latest_calling = {
                "ticket_id": latest_row[0],
                "ticket_number": latest_row[1],
                "patient_name": p_full,
                "patient_name_masked": masked_name,
                "room_name": latest_row[3],
                "room_number": latest_row[4],
                "floor": latest_row[5],
                "called_at": latest_row[6],
                "called_at_str": latest_row[6].strftime("%H:%M:%S") if latest_row[6] else "",
                "is_emergency": (latest_row[7] >= 2),
                "doctor_name": latest_row[8] or "Bác sĩ trực"
            }

        # 2. Danh sách trạng thái từng phòng khám
        r_query = """
            SELECT r.id, r.code, r.name, r.room_number, r.floor, r.type,
                   u.full_name AS doctor_name
            FROM rooms r
            LEFT JOIN doctor_schedules ds ON r.id = ds.room_id AND ds.work_date = ? AND ds.is_active = 1
            LEFT JOIN users u ON ds.doctor_id = u.id
            WHERE r.is_active = 1 AND (r.is_restricted = 0 OR r.is_restricted IS NULL)
        """
        r_params = [today_vn]
        if floor:
            r_query += " AND r.floor = ?"
            r_params.append(floor)
        r_query += " ORDER BY r.floor, r.code"

        cursor.execute(r_query, r_params)
        room_rows = cursor.fetchall()

        rooms_status = []
        for r in room_rows:
            rid, rcode, rname, rnum, rfloor, rtype, dname = r

            # Bệnh nhân đang gọi hoặc đang khám
            cursor.execute("""
                SELECT TOP 1 ticket_number, patient_name, status
                FROM tickets
                WHERE current_room_id = ? AND visit_date = ? AND status IN ('calling', 'in_progress', 'cls_in_progress')
                ORDER BY CASE WHEN status = 'calling' THEN 1 ELSE 2 END, called_at DESC
            """, (rid, today_vn))
            curr = cursor.fetchone()

            # Bệnh nhân chuẩn bị kế tiếp
            cursor.execute("""
                SELECT TOP 1 ticket_number, patient_name
                FROM tickets
                WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic', 'emergency_override')
                ORDER BY 
                    CASE 
                        WHEN status = 'emergency_override' THEN 1
                        WHEN status = 'returned_to_clinic' THEN 2 
                        ELSE 3 
                    END,
                    priority_level DESC,
                    id ASC
            """, (rid, today_vn))
            nxt = cursor.fetchone()

            # Tổng số chờ
            cursor.execute("""
                SELECT COUNT(*)
                FROM tickets
                WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic', 'emergency_override')
            """, (rid, today_vn))
            waiting_cnt = cursor.fetchone()[0]

            rooms_status.append({
                "room_id": rid,
                "room_code": rcode,
                "room_name": rname,
                "room_number": rnum,
                "floor": rfloor,
                "type": rtype,
                "doctor_name": dname or ("Bác sĩ trực cấp cứu" if rtype == "emergency" else "Bác sĩ chuyên khoa"),
                "current_ticket": curr[0] if curr else "---",
                "current_patient": curr[1] if curr else "",
                "current_status": curr[2] if curr else "idle",
                "next_ticket": nxt[0] if nxt else "---",
                "next_patient": nxt[1] if nxt else "",
                "waiting_count": waiting_cnt
            })

        return {
            "latest_calling": latest_calling,
            "rooms": rooms_status,
            "total_rooms": len(rooms_status),
            "timestamp": get_vn_now().strftime("%H:%M:%S - %d/%m/%Y")
        }
    finally:
        conn.close()


def skip_ticket(ticket_id: int, user_id: int, username: str) -> bool:
    """Bỏ qua lượt nếu gọi quá số lần mà bệnh nhân không có mặt."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets
            SET status = 'skipped'
            WHERE id = ?
        """, (ticket_id,))
        conn.commit()
        log_audit(user_id, username, "SKIP_TICKET", "TICKET", str(ticket_id), "Bỏ qua lượt khám (vắng mặt)")
        return True
    finally:
        conn.close()

"""Service quản lý cấp số hàng đợi, luân chuyển bệnh nhân giữa phòng khám lâm sàng
và phòng cận lâm sàng (lấy máu, đo hô hấp, X-Quang...) trên MS SQL Server.
"""
from __future__ import annotations

from datetime import datetime, date
import db
from auth import log_audit


def get_all_rooms(room_type: str | None = None) -> list[dict]:
    """Lấy danh sách tất cả phòng khám hoặc phòng cận lâm sàng."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT r.id, r.code, r.name, r.room_number, r.floor, r.type, r.prefix, 
                   r.department_id, d.name as department_name, r.instructions, r.is_active
            FROM rooms r
            LEFT JOIN departments d ON r.department_id = d.id
            WHERE r.is_active = 1
        """
        params = []
        if room_type:
            query += " AND r.type = ?"
            params.append(room_type)
        query += " ORDER BY r.floor, r.room_number"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            {
                "id": r[0], "code": r[1], "name": r[2], "room_number": r[3],
                "floor": r[4], "type": r[5], "prefix": r[6], "department_id": r[7],
                "department_name": r[8] or "", "instructions": r[9] or "", "is_active": bool(r[10])
            }
            for r in rows
        ]
    finally:
        conn.close()


def issue_ticket(room_id: int, patient_name: str, patient_phone: str, patient_notes: str = "", priority_level: int = 0) -> dict:
    """Cấp số thứ tự mới cho bệnh nhân tại một phòng khám/kiosk.
    
    Quy tắc số thứ tự: Reset theo ngày, dạng: <PREFIX>-<SEQ:03d> (VD: PK301-001)
    """
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today()

        # 1. Lấy thông tin phòng
        cursor.execute("SELECT id, name, room_number, floor, prefix, instructions FROM rooms WHERE id = ?", (room_id,))
        room = cursor.fetchone()
        if not room:
            raise ValueError(f"Không tìm thấy phòng với ID {room_id}")

        rid, rname, rnumber, floor, prefix, instructions = room

        # 2. Tính số thứ tự trong ngày của phòng đó
        cursor.execute("""
            SELECT ISNULL(MAX(daily_seq), 0) + 1 
            FROM tickets 
            WHERE initial_room_id = ? AND visit_date = ?
        """, (room_id, today))
        next_seq = cursor.fetchone()[0]

        ticket_code = f"{prefix}-{next_seq:03d}"

        # 3. Chèn vé mới vào bảng tickets
        cursor.execute("""
            INSERT INTO tickets (ticket_number, daily_seq, patient_name, patient_phone, patient_notes,
                                 initial_room_id, current_room_id, status, priority_level, visit_date, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting', ?, ?, GETDATE())
        """, (ticket_code, next_seq, patient_name, patient_phone, patient_notes, room_id, room_id, priority_level, today))
        ticket_id = cursor.fetchone()[0]

        # 4. Đếm số người đang chờ trước người này
        cursor.execute("""
            SELECT COUNT(*) 
            FROM tickets 
            WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic')
              AND (priority_level > ? OR (priority_level = ? AND id < ?))
        """, (room_id, today, priority_level, priority_level, ticket_id))
        waiting_ahead = cursor.fetchone()[0]

        conn.commit()

        log_audit(None, "KIOSK", "ISSUE_TICKET", "TICKET", str(ticket_id), f"Cấp vé {ticket_code} ({patient_name})")

        return {
            "ticket_id": ticket_id,
            "ticket_number": ticket_code,
            "daily_seq": next_seq,
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "room_id": room_id,
            "room_name": rname,
            "room_number": rnumber,
            "floor": floor,
            "instructions": instructions or "",
            "waiting_ahead": waiting_ahead,
            "priority_level": priority_level,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_room_queue(room_id: int) -> dict:
    """Lấy danh sách hàng đợi hiện tại của một phòng (ưu tiên returned_to_clinic & priority)."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today()

        cursor.execute("""
            SELECT t.id, t.ticket_number, t.daily_seq, t.patient_name, t.patient_phone, t.patient_notes,
                   t.initial_room_id, t.current_room_id, t.status, t.priority_level, t.created_at, t.called_at,
                   r_init.name as initial_room_name, r_init.room_number as initial_room_number
            FROM tickets t
            LEFT JOIN rooms r_init ON t.initial_room_id = r_init.id
            WHERE t.current_room_id = ? AND t.visit_date = ? AND t.status NOT IN ('completed', 'skipped')
            ORDER BY 
                CASE 
                    WHEN t.status = 'calling' THEN 1
                    WHEN t.status = 'in_progress' THEN 2
                    WHEN t.status = 'cls_in_progress' THEN 2
                    WHEN t.status = 'returned_to_clinic' THEN 3
                    WHEN t.status = 'waiting' THEN 4
                    ELSE 5
                END,
                t.priority_level DESC,
                t.id ASC
        """, (room_id, today))
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
                "initial_room_number": r[13] or ""
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
    """Bác sĩ hoặc KTV bấm Gọi bệnh nhân tiếp theo."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today()

        # Tìm bệnh nhân tiếp theo: ưu tiên priority cao nhất, hoặc returned_to_clinic trước
        cursor.execute("""
            SELECT TOP 1 id, ticket_number, patient_name, patient_phone
            FROM tickets
            WHERE current_room_id = ? AND visit_date = ? AND status IN ('waiting', 'returned_to_clinic')
            ORDER BY 
                CASE WHEN status = 'returned_to_clinic' THEN 1 ELSE 2 END,
                priority_level DESC,
                id ASC
        """, (room_id, today))
        row = cursor.fetchone()
        if not row:
            return None

        ticket_id, ticket_num, p_name, p_phone = row

        # Đổi trạng thái vé sang calling
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

        cursor.execute("""
            SELECT type FROM rooms WHERE id = ?
        """, (row[0],))
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
    """Bác sĩ chỉ định cận lâm sàng (lấy máu, đo hô hấp, X-Quang...).
    
    Tự động:
    1. Tạo y lệnh trong clinical_orders.
    2. Cấp số thứ tự tại phòng cận lâm sàng đó.
    3. Chuyển current_room_id của vé sang phòng cận lâm sàng với status = 'waiting'.
    4. Trả về thông tin hướng dẫn đường đi để in phiếu / hiển thị / gửi SMS.
    """
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        today = date.today()

        # Lấy thông tin phòng cận lâm sàng
        cursor.execute("SELECT name, room_number, floor, prefix, instructions FROM rooms WHERE id = ?", (target_room_id,))
        cls_room = cursor.fetchone()
        if not cls_room:
            raise ValueError(f"Không tìm thấy phòng cận lâm sàng ID {target_room_id}")

        cls_name, cls_number, cls_floor, cls_prefix, cls_inst = cls_room

        # Tạo số thứ tự tại phòng CLS
        cursor.execute("""
            SELECT ISNULL(MAX(daily_seq), 0) + 1
            FROM clinical_orders o
            JOIN tickets t ON o.ticket_id = t.id
            WHERE o.target_room_id = ? AND t.visit_date = ?
        """, (target_room_id, today))
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
    """Kỹ thuật viên tại phòng CLS hoàn thành dịch vụ:
    
    1. Đánh dấu order là 'completed' và lưu kết quả.
    2. Chuyển vé bệnh nhân QUAY LẠI phòng khám ban đầu (initial_room_id).
    3. Đặt trạng thái = 'returned_to_clinic' và priority_level = 1 (Ưu tiên khám lại để bác sĩ đọc kết quả).
    """
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

        # Đánh dấu y lệnh hoàn tất
        cursor.execute("""
            UPDATE clinical_orders
            SET status = 'completed', results = ?, completed_at = GETDATE()
            WHERE id = ?
        """, (results, order_id))

        # Đưa vé bệnh nhân QUAY LẠI phòng khám ban đầu với cờ ưu tiên 1
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
    """Bác sĩ kết thúc lượt khám và xuất viện / cho về."""
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

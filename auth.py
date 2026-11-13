"""Module bảo mật, xác thực người dùng, mã hóa mật khẩu bcrypt và phân quyền RBAC theo hành động.

Tuân thủ an toàn thông tin y tế theo Nghị định 13/2023/NĐ-CP:
1. Mã hóa mật khẩu chuẩn Bcrypt (kèm salt 12 rounds), chống tấn công Rainbow Table/GPU.
2. Hỗ trợ tự động nhận diện và migrate các hash mật khẩu cũ (PBKDF2/scrypt) khi đăng nhập thành công.
3. Phân quyền theo từng hành động cụ thể (Action-based RBAC) cho từng vai trò y tế.
4. Nhật ký kiểm toán an toàn y tế (Audit Trail) chi tiết: Ai, Thao tác gì, Đối tượng nào, Thời điểm nào, Địa chỉ IP.
"""
from __future__ import annotations

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
import db


# ═══════════════════════════════════════════════════════════════════════════
# CẤU HÌNH BẢO MẬT & PHÂN QUYỀN RBAC THEO HÀNH ĐỘNG
# ═══════════════════════════════════════════════════════════════════════════
BCRYPT_ROUNDS = 12
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Ma trận quyền hạn chi tiết (Action-based RBAC Matrix)
PERMISSIONS_MATRIX: dict[str, list[str]] = {
    "admin": ["*"],  # Toàn quyền hệ thống
    "manager": [
        "queue.view_all",
        "schedule.view",
        "schedule.manage",
        "reports.view",
        "users.view",
        "users.create",
        "audit.view",
        "inventory.view",
    ],
    "doctor": [
        "queue.view_assigned",
        "ticket.call",
        "ticket.start",
        "ticket.complete",
        "ticket.skip",
        "exam.create",
        "exam.view",
        "exam.update",
        "prescription.create",
        "prescription.view",
        "order_cls.create",
        "drug.search",
        "drug.interaction_check",
        "patient.view_history",
    ],
    "technician": [
        "order_cls.view",
        "order_cls.start",
        "order_cls.complete",
        "order_cls.view_results",
        "queue.view_assigned",
    ],
    "nurse": [
        "queue.view_assigned",
        "vital_signs.input",
        "ticket.guide",
        "patient.search",
    ],
    "cashier": [
        "invoice.view",
        "invoice.collect",
        "ticket.status_update",
    ],
    "receptionist": [
        "ticket.issue",
        "patient.register",
        "patient.search",
        "patient.merge",
        "queue.view_all",
    ],
}


def has_permission(role: str, action: str) -> bool:
    """Kiểm tra một vai trò có quyền thực hiện một hành động cụ thể hay không."""
    if not role:
        return False
    user_perms = PERMISSIONS_MATRIX.get(role.lower(), [])
    if "*" in user_perms:
        return True
    return action in user_perms


# ═══════════════════════════════════════════════════════════════════════════
# MÃ HÓA & KIỂM TRA MẬT KHẨU
# ═══════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Băm mật khẩu bằng Bcrypt với Salt 12 rounds (hoặc scrypt chuẩn Python stdlib nếu chưa có bcrypt)."""
    if HAS_BCRYPT:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
        return hashed.decode("utf-8")
    
    # Dự phòng an toàn dùng hashlib.scrypt chuẩn OWASP (không cần cài thêm C library)
    salt_bytes = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt_bytes, n=16384, r=8, p=1, dklen=64)
    return f"$scrypt$16384$8$1${salt_bytes.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str, salt: str = "") -> bool:
    """Xác thực mật khẩu thông minh: hỗ trợ cả Bcrypt mới, scrypt và PBKDF2 cũ."""
    if not stored_hash:
        return False

    # 1. Kiểm tra nếu là hash Bcrypt (bắt đầu bằng $2a$, $2b$ hoặc $2y$)
    if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
        if HAS_BCRYPT:
            try:
                return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
            except Exception:
                return False
        return False

    # 2. Kiểm tra nếu là hash scrypt ($scrypt$n$r$p$salt$hash)
    if stored_hash.startswith("$scrypt$"):
        try:
            parts = stored_hash.split("$")[1:]
            # format: scrypt, n, r, p, salt_hex, hash_hex
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt_b = bytes.fromhex(parts[4])
            expected = parts[5]
            derived = hashlib.scrypt(password.encode("utf-8"), salt=salt_b, n=n, r=r, p=p, dklen=64).hex()
            return hmac.compare_digest(derived, expected)
        except Exception:
            return False

    # 3. Dự phòng kiểm tra hash PBKDF2 cũ (để migrate người dùng không bị mất mật khẩu)
    if salt:
        try:
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000, dklen=64)
            return hmac.compare_digest(key.hex(), stored_hash)
        except Exception:
            pass

    return False


# ═══════════════════════════════════════════════════════════════════════════
# XÁC THỰC NGƯỜI DÙNG & GHI NHẬN AUDIT LOG
# ═══════════════════════════════════════════════════════════════════════════

def authenticate_user(username: str, password: str, client_ip: str | None = None) -> dict:
    """Xác thực tài khoản nhân viên y tế, kiểm tra khóa và tự động nâng cấp hash sang bcrypt."""
    conn = db.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.password_hash, u.salt, u.full_name, u.role, 
                   u.department_id, u.room_id, u.is_active, u.failed_login_count, u.locked_until,
                   d.name as department_name, r.name as room_name, r.room_number, r.floor
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            LEFT JOIN rooms r ON u.room_id = r.id
            WHERE u.username = ?
        """, (username,))
        row = cursor.fetchone()

        if not row:
            log_audit(None, username, "LOGIN_FAILED", "USER", None, "Tài khoản không tồn tại", client_ip)
            return {"success": False, "user": None, "error": "Tài khoản hoặc mật khẩu không chính xác."}

        (uid, uname, pwd_hash, salt, full_name, role, dept_id, room_id, is_active,
         failed_count, locked_until, dept_name, room_name, room_num, floor) = row

        if not is_active:
            log_audit(uid, uname, "LOGIN_BLOCKED", "USER", str(uid), "Tài khoản đã bị vô hiệu hóa", client_ip)
            return {"success": False, "user": None, "error": "Tài khoản này đã bị khóa bởi Quản trị viên."}

        now = datetime.now()
        if locked_until and locked_until > now:
            remaining = int((locked_until - now).total_seconds() / 60) + 1
            log_audit(uid, uname, "LOGIN_LOCKED", "USER", str(uid), f"Đang bị khóa tạm thời ({remaining} phút)", client_ip)
            return {"success": False, "user": None, "error": f"Tài khoản đang tạm khóa do nhập sai nhiều lần. Thử lại sau {remaining} phút."}

        # Xác thực mật khẩu
        if verify_password(password, pwd_hash, salt):
            # Nếu hash cũ chưa phải Bcrypt, tự động nâng cấp sang Bcrypt ngay trong database
            if not pwd_hash.startswith(("$2a$", "$2b$", "$2y$")):
                new_bcrypt_hash = hash_password(password)
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = ?, failed_login_count = 0, locked_until = NULL 
                    WHERE id = ?
                """, (new_bcrypt_hash, uid))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET failed_login_count = 0, locked_until = NULL 
                    WHERE id = ?
                """, (uid,))
            conn.commit()

            user_data = {
                "id": uid,
                "username": uname,
                "full_name": full_name,
                "role": role,
                "department_id": dept_id,
                "department_name": dept_name or "",
                "room_id": room_id,
                "room_name": room_name or "",
                "room_number": room_num or "",
                "floor": floor or 1,
            }

            log_audit(uid, uname, "LOGIN_SUCCESS", "USER", str(uid), f"Đăng nhập thành công vai trò {role}", client_ip)
            return {"success": True, "user": user_data, "error": None}

        # Sai mật khẩu -> Tăng số lần thử
        new_failed = (failed_count or 0) + 1
        new_locked_until = None
        if new_failed >= MAX_FAILED_ATTEMPTS:
            new_locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            err_msg = f"Đã nhập sai quá {MAX_FAILED_ATTEMPTS} lần! Tài khoản bị tạm khóa {LOCKOUT_MINUTES} phút."
            log_audit(uid, uname, "ACCOUNT_LOCKED", "USER", str(uid), f"Khóa tạm {LOCKOUT_MINUTES}p do sai pass {new_failed} lần", client_ip)
        else:
            left_attempts = MAX_FAILED_ATTEMPTS - new_failed
            err_msg = f"Mật khẩu không chính xác. Bạn còn {left_attempts} lần thử trước khi bị khóa."
            log_audit(uid, uname, "LOGIN_FAILED", "USER", str(uid), f"Sai mật khẩu (lần {new_failed})", client_ip)

        cursor.execute("""
            UPDATE users 
            SET failed_login_count = ?, locked_until = ? 
            WHERE id = ?
        """, (new_failed, new_locked_until, uid))
        conn.commit()

        return {"success": False, "user": None, "error": err_msg}
    finally:
        conn.close()


def log_audit(user_id: int | None, username: str | None, action: str, 
              target_type: str | None = None, target_id: str | None = None, 
              details: str | None = None, ip_address: str | None = None,
              patient_id: int | None = None) -> None:
    """Ghi vết kiểm toán an toàn y tế (Audit Trail) - Bắt buộc theo Nghị định 13/2023/NĐ-CP."""
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, action, target_type, target_id, details, ip_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE())
        """, (user_id, username, action, target_type, target_id, details, ip_address))
        conn.commit()
        conn.close()
    except Exception as e:
        # Ghi log file dự phòng nếu DB tạm ngắt
        print(f"[AUDIT LOG ERROR] {e} | Action: {action} by {username}")


# ═══════════════════════════════════════════════════════════════════════════
# QUẢN TRỊ CÁN BỘ NHÂN VIÊN & PHÂN CA TRỰC BỆNH VIỆN ATUS
# ═══════════════════════════════════════════════════════════════════════════

def get_all_departments() -> list[dict]:
    """Lấy danh sách toàn bộ các Khoa / Chuyên khoa của bệnh viện."""
    conn = db.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, floor, phone FROM departments ORDER BY floor ASC, id ASC")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_staff_users(role_filter: str | None = None) -> list[dict]:
    """Lấy danh sách cán bộ nhân viên bệnh viện kèm thông tin khoa phòng."""
    conn = db.get_db_connection()
    try:
        cur = conn.cursor()
        query = """
            SELECT u.id, u.username, u.full_name, u.role, u.department_id, d.name AS department_name,
                   u.room_id, r.name AS room_name, r.code AS room_code,
                   u.is_active, u.failed_login_count, u.locked_until, u.created_at
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            LEFT JOIN rooms r ON u.room_id = r.id
        """
        params = []
        if role_filter:
            query += " WHERE u.role = ?"
            params.append(role_filter)
        query += " ORDER BY u.role ASC, u.full_name ASC"
        
        cur.execute(query, tuple(params))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def create_staff_user(
    username: str,
    password: str,
    full_name: str,
    role: str,
    department_id: int | None = None,
    room_id: int | None = None,
    created_by: str = "admin"
) -> dict:
    """Thêm cán bộ nhân viên y tế mới vào hệ thống (Mã hóa Bcrypt + Ghi vết Audit)."""
    username = username.strip().lower()
    full_name = full_name.strip()
    
    if not username or not password or not full_name:
        raise ValueError("Vui lòng điền đầy đủ Tên đăng nhập, Mật khẩu và Họ tên cán bộ nhân viên!")
    
    valid_roles = ["doctor", "nurse", "technician", "pharmacist", "cashier", "manager", "admin"]
    if role not in valid_roles:
        raise ValueError(f"Vai trò không hợp lệ ({role}). Danh sách hợp lệ: {', '.join(valid_roles)}")
    
    pwd_hash = hash_password(password)
    
    conn = db.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            raise ValueError(f"Tên tài khoản '{username}' đã tồn tại trong hệ thống. Vui lòng chọn tên khác!")
        
        cur.execute("""
            INSERT INTO users (username, password_hash, salt, full_name, role, department_id, room_id, is_active, failed_login_count, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, '', ?, ?, ?, ?, 1, 0, GETDATE())
        """, (username, pwd_hash, full_name, role, department_id, room_id))
        new_id = cur.fetchone()[0]
        conn.commit()
        
        log_audit(
            user_id=None,
            username=created_by,
            action="CREATE_USER",
            target_type="USER",
            target_id=str(new_id),
            details=f"Tạo mới tài khoản cán bộ: {full_name} ({username}) - Vai trò: {role.upper()}"
        )
        return {
            "success": True,
            "id": new_id,
            "username": username,
            "full_name": full_name,
            "role": role
        }
    finally:
        conn.close()


def update_staff_status(user_id: int, is_active: bool, updated_by: str = "admin") -> bool:
    """Khóa hoặc Mở khóa tài khoản nhân viên."""
    conn = db.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET is_active = ?, failed_login_count = 0, locked_until = NULL 
            WHERE id = ?
        """, (1 if is_active else 0, user_id))
        conn.commit()
        
        log_audit(
            user_id=None,
            username=updated_by,
            action="UPDATE_USER_STATUS",
            target_type="USER",
            target_id=str(user_id),
            details=f"Cập nhật trạng thái tài khoản: {'Kích hoạt' if is_active else 'Khóa'}"
        )
        return True
    finally:
        conn.close()


def schedule_staff_shift(
    doctor_id: int,
    room_id: int,
    work_date,
    shift: str,
    start_time: str = "07:00",
    end_time: str = "11:30",
    max_patients: int = 40,
    created_by: str = "admin"
) -> dict:
    """Xếp ca làm việc cho bác sĩ/nhân viên y tế vào phòng khám theo buổi."""
    valid_shifts = ["morning", "afternoon", "night", "full_day"]
    if shift not in valid_shifts:
        raise ValueError(f"Ca làm việc không hợp lệ ({shift}). Hợp lệ: {valid_shifts}")
    
    conn = db.get_db_connection()
    try:
        cur = conn.cursor()
        # Kiểm tra trùng ca
        cur.execute("""
            SELECT id FROM doctor_schedules
            WHERE doctor_id = ? AND work_date = ? AND shift = ?
        """, (doctor_id, work_date, shift))
        if cur.fetchone():
            raise ValueError(f"Bác sĩ đã có lịch trực trong ca {shift} ngày {work_date}!")
        
        cur.execute("""
            INSERT INTO doctor_schedules (doctor_id, room_id, work_date, shift, start_time, end_time, max_patients, is_active, created_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
        """, (doctor_id, room_id, work_date, shift, start_time, end_time, max_patients))
        schedule_id = cur.fetchone()[0]
        conn.commit()
        
        log_audit(
            user_id=None,
            username=created_by,
            action="SCHEDULE_SHIFT",
            target_type="SCHEDULE",
            target_id=str(schedule_id),
            details=f"Xếp ca {shift} ngày {work_date} cho nhân viên ID {doctor_id} tại phòng ID {room_id}"
        )
        return {"success": True, "schedule_id": schedule_id}
    finally:
        conn.close()


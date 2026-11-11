"""Dịch vụ bảo mật, xác thực người dùng và mã hóa mật khẩu an toàn.

Sử dụng thuật toán chuẩn công nghiệp: PBKDF2-HMAC-SHA256 kết hợp Salt ngẫu nhiên 32-byte.
Chống tấn công từ điển, Rainbow Table và Brute-force.
Hỗ trợ khóa tài khoản tạm thời khi đăng nhập sai quá số lần quy định.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
import db


ITERATIONS = 120_000
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def generate_salt() -> str:
    """Tạo salt ngẫu nhiên bảo mật cao (hex 32-byte = 64 ký tự)."""
    return secrets.token_hex(32)


def hash_password(password: str, salt: str) -> str:
    """Băm mật khẩu kết hợp Salt dùng PBKDF2-HMAC-SHA256."""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
        dklen=64
    )
    return key.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Xác thực mật khẩu an toàn theo cơ chế constant-time compare."""
    computed_hash = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, expected_hash)


def authenticate_user(username: str, password: str, client_ip: str | None = None) -> dict:
    """Xác thực tài khoản và kiểm tra trạng thái khóa.

    Returns:
        dict: {"success": bool, "user": dict | None, "error": str | None}
    """
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

        # Kiểm tra mật khẩu
        if verify_password(password, salt, pwd_hash):
            # Thành công -> Reset số lần sai và thời gian khóa
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
                "floor": floor or 0
            }
            log_audit(uid, uname, "LOGIN_SUCCESS", "USER", str(uid), f"Đăng nhập vai trò {role}", client_ip)
            return {"success": True, "user": user_data, "error": None}
        else:
            # Sai mật khẩu -> Tăng đếm
            new_failed = failed_count + 1
            new_locked = None
            err_msg = "Tài khoản hoặc mật khẩu không chính xác."

            if new_failed >= MAX_FAILED_ATTEMPTS:
                new_locked = now + timedelta(minutes=LOCKOUT_MINUTES)
                err_msg = f"Đăng nhập sai quá {MAX_FAILED_ATTEMPTS} lần! Tài khoản tạm thời bị khóa {LOCKOUT_MINUTES} phút."

            cursor.execute("""
                UPDATE users 
                SET failed_login_count = ?, locked_until = ? 
                WHERE id = ?
            """, (new_failed, new_locked, uid))
            conn.commit()

            log_audit(uid, uname, "LOGIN_FAILED_PASSWORD", "USER", str(uid), f"Sai lần {new_failed}", client_ip)
            return {"success": False, "user": None, "error": err_msg}

    finally:
        conn.close()


def log_audit(user_id: int | None, username: str | None, action: str, 
              target_type: str | None = None, target_id: str | None = None, 
              details: str | None = None, ip_address: str | None = None) -> None:
    """Ghi nhận nhật ký kiểm toán (Audit Trail) phục vụ bảo mật y tế."""
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, action, target_type, target_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, action, target_type, target_id, details, ip_address))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Lỗi ghi Audit Log:", e)

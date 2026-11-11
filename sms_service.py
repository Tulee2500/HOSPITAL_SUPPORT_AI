"""Module hỗ trợ gửi tin nhắn SMS / Email thông báo xác nhận đặt lịch khám.

Mặc định: Simulation mode (lưu log và trả về tin nhắn mẫu chuẩn SMS Brandname 'BV-ATUS').
Có thể cấu hình Twilio qua biến môi trường (.env):
  TWILIO_ACCOUNT_SID=...
  TWILIO_AUTH_TOKEN=...
  TWILIO_PHONE_NUMBER=...
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

SMS_LOG_FILE = Path("data/sms_logs.txt")


def format_sms_message(code: str, name: str, dept: str, date: str) -> str:
    """Tạo nội dung tin nhắn SMS xác nhận lịch hẹn chuẩn thương hiệu y tế."""
    return (
        f"[BV ATUS] Chao {name}, ban da dang ky kham thanh cong! "
        f"Ma phieu: {code}. Khoa: {dept}. Ngay hen: {date}. "
        f"Vui long den truoc 15p tai Quay tiep don Tang 1. Hotline: 024.7777.9999"
    )


def send_appointment_sms(code: str, name: str, phone: str, dept: str, date: str) -> dict:
    """Gửi SMS thông báo lịch khám.
    
    Returns:
        dict: {"success": bool, "mode": "twilio" | "simulated", "message": str, "phone": str}
    """
    message_body = format_sms_message(code, name, dept, str(date))
    
    # Kiểm tra cấu hình Twilio nếu có
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if account_sid and auth_token and from_number:
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            
            # Format số điện thoại Việt Nam sang E.164 (+84...)
            formatted_phone = phone.strip()
            if formatted_phone.startswith("0"):
                formatted_phone = "+84" + formatted_phone[1:]
            elif not formatted_phone.startswith("+"):
                formatted_phone = "+84" + formatted_phone

            msg = client.messages.create(
                body=message_body,
                from_=from_number,
                to=formatted_phone
            )
            _log_sms(code, name, phone, message_body, status=f"SENT_TWILIO (SID: {msg.sid})")
            return {
                "success": True,
                "mode": "twilio",
                "message": message_body,
                "phone": formatted_phone,
                "sid": msg.sid
            }
        except Exception as e:
            # Fallback sang simulation nếu lỗi Twilio
            _log_sms(code, name, phone, message_body, status=f"TWILIO_ERROR: {e}")
            return {
                "success": False,
                "mode": "twilio_failed",
                "message": message_body,
                "phone": phone,
                "error": str(e)
            }

    # Simulation mode
    _log_sms(code, name, phone, message_body, status="SIMULATED_SUCCESS")
    return {
        "success": True,
        "mode": "simulated",
        "message": message_body,
        "phone": phone
    }


def _log_sms(code: str, name: str, phone: str, message: str, status: str) -> None:
    SMS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SMS_LOG_FILE, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] [{status}] Code: {code} | Phone: {phone} | Name: {name}\n")
        f.write(f"Content: {message}\n\n")

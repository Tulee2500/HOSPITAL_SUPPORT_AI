"""Module lưu trữ đăng ký khám bệnh vào file CSV.

File lưu tại: data/registrations.csv
Mỗi lần ghi sẽ append một dòng mới.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

REG_FILE    = Path("data/registrations.csv")
REG_HEADERS = ["ma_phieu", "ho_ten", "so_dien_thoai", "khoa", "ngay_hen", "ly_do", "thoi_gian_dk"]


def save_registration(
    code:  str,
    name:  str,
    phone: str,
    dept:  str,
    date:  str,
    notes: str,
) -> None:
    """Lưu một lượt đăng ký khám vào CSV. Tự tạo file + header nếu chưa tồn tại."""
    REG_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not REG_FILE.exists() or REG_FILE.stat().st_size == 0
    with open(REG_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=REG_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "ma_phieu":        code,
            "ho_ten":          name,
            "so_dien_thoai":   phone,
            "khoa":            dept,
            "ngay_hen":        str(date),
            "ly_do":           notes,
            "thoi_gian_dk":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        })


def load_registrations(limit: int = 50) -> list[dict]:
    """Đọc tối đa `limit` dòng mới nhất từ CSV. Trả về [] nếu chưa có file."""
    if not REG_FILE.exists():
        return []
    with open(REG_FILE, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return rows[-limit:]  # lấy dòng mới nhất


def count_registrations() -> int:
    """Đếm tổng số lượt đăng ký."""
    if not REG_FILE.exists():
        return 0
    with open(REG_FILE, encoding="utf-8-sig") as f:
        return max(0, sum(1 for _ in f) - 1)   # trừ header

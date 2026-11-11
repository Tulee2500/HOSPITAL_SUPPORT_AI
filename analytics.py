"""Module lưu vết (audit log) và phân tích (analytics) tương tác của trợ lý tiếp đón.

Ghi nhận:
- Lượt chat, ý định (intent: symptom, procedure, emergency, other)
- Khoa phòng được gợi ý
- Tỷ lệ câu hỏi khẩn cấp
- Thời gian tương tác
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

ANALYTICS_FILE = Path("data/chat_analytics.csv")
ANALYTICS_HEADERS = ["timestamp", "user_query", "intent", "department", "is_emergency"]


def log_interaction(query: str, intent: str, department: str | None = None, is_emergency: bool = False) -> None:
    """Lưu 1 lượt tương tác của người dùng để phục vụ thống kê."""
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not ANALYTICS_FILE.exists() or ANALYTICS_FILE.stat().st_size == 0
    with open(ANALYTICS_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ANALYTICS_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_query": query.replace("\n", " ").strip()[:200],
            "intent": intent,
            "department": department or "",
            "is_emergency": "true" if is_emergency else "false"
        })


def get_analytics_summary() -> dict:
    """Tổng hợp số liệu thống kê cho Admin Dashboard."""
    if not ANALYTICS_FILE.exists():
        return {
            "total_queries": 0,
            "intent_counts": {},
            "dept_counts": {},
            "emergency_count": 0,
            "recent_logs": []
        }

    with open(ANALYTICS_FILE, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    intent_counts: dict[str, int] = {}
    dept_counts: dict[str, int] = {}
    emergency_count = 0

    for r in rows:
        intent = r.get("intent", "other")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

        dept = r.get("department")
        if dept:
            dept_counts[dept] = dept_counts.get(dept, 0) + 1

        if r.get("is_emergency", "").lower() == "true":
            emergency_count += 1

    return {
        "total_queries": total,
        "intent_counts": intent_counts,
        "dept_counts": dept_counts,
        "emergency_count": emergency_count,
        "recent_logs": rows[-50:]  # 50 lượt gần nhất
    }

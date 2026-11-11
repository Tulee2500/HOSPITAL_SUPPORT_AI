"""Điều phối toàn bộ luồng: khẩn cấp → phân loại → (khoa | RAG streaming) → trả lời.

Thay đổi so với phiên bản cũ:
- history giờ là list[{"role": "user"|"assistant", "content": str}] (multi-turn thực sự)
- Kết quả trả về có thêm key "stream": Generator | None
  + stream != None  → procedure intent, app dùng st.write_stream()
  + stream == None  → tất cả intent khác, app dùng st.markdown(text)

Chạy thử trong terminal:  python assistant.py
"""
from __future__ import annotations

from typing import Generator

from rag import Retriever
from safety import EMERGENCY_MESSAGE, check_emergency_rules
from triage import answer_procedure_stream, route_message, suggest_department
from analytics import log_interaction

_retriever = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# ──────────────────── Bản đồ khoa → vị trí 3D ─────────────────────────────
DEPARTMENT_MAPPING = {
    "Cấp cứu": {
        "floor": 1, "room_name": "Khoa Cấp Cứu 24/7 (ICU)", "room_x": -9.5,
        "instructions": "Tại Tầng 1 (Khu vực màu đỏ khẩn cấp bên trái sảnh chính). Có lối đi riêng cho xe cấp cứu.",
    },
    "Nội tổng quát": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Đi thang máy trung tâm lên Tầng 3, rẽ trái vào phòng 301 (Nội - Ngoại Tổng Quát).",
    },
    "Ngoại tổng quát": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Đi thang máy trung tâm lên Tầng 3, rẽ trái vào phòng 301 (Nội - Ngoại Tổng Quát).",
    },
    "Tim mạch": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Lên Tầng 3 - Khu Khám Nội Tim Mạch (phòng 301B).",
    },
    "Hô hấp": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Lên Tầng 3 - Khu Khám Nội Hô Hấp (phòng 301C).",
    },
    "Tiêu hóa": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Lên Tầng 3 - Khu Khám Tiêu Hóa (phòng 301D).",
    },
    "Thần kinh": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Lên Tầng 3 - Phòng Chuyên Khoa Thần Kinh (phòng 301E).",
    },
    "Cơ xương khớp": {
        "floor": 3, "room_name": "Khám Nội - Ngoại Tổng Quát", "room_x": -10,
        "instructions": "Lên Tầng 3 - Phòng Khám Ngoại Cơ Xương Khớp (phòng 301A).",
    },
    "Mắt": {
        "floor": 3, "room_name": "Chuyên Khoa Mắt & TMH", "room_x": 1,
        "instructions": "Lên Tầng 3, đối diện sảnh thang máy: Phòng 302 - Chuyên Khoa Mắt.",
    },
    "Tai mũi họng": {
        "floor": 3, "room_name": "Chuyên Khoa Mắt & TMH", "room_x": 1,
        "instructions": "Lên Tầng 3, phòng 303 - Chuyên Khoa Tai Mũi Họng.",
    },
    "Răng hàm mặt": {
        "floor": 3, "room_name": "Răng Hàm Mặt & Da Liễu", "room_x": 10.5,
        "instructions": "Lên Tầng 3, rẽ phải vào dãy phòng 304 - Răng Hàm Mặt.",
    },
    "Da liễu": {
        "floor": 3, "room_name": "Răng Hàm Mặt & Da Liễu", "room_x": 10.5,
        "instructions": "Lên Tầng 3, rẽ phải vào dãy phòng 305 - Da Liễu.",
    },
    "Sản phụ khoa": {
        "floor": 4, "room_name": "Khoa Sản Phụ Khoa", "room_x": -8,
        "instructions": "Đi thang máy lên Tầng 4, toàn bộ cánh trái là Khoa Sản Phụ Khoa & Phòng sinh.",
    },
    "Nhi khoa": {
        "floor": 4, "room_name": "Khoa Nhi & Khu Tiêm Chủng", "room_x": 8,
        "instructions": "Đi thang máy lên Tầng 4, rẽ phải là Khoa Nhi & Phòng Tiêm chủng cho bé.",
    },
    "Chẩn đoán hình ảnh": {
        "floor": 2, "room_name": "Chẩn Đoán Hình Ảnh (MRI / CT)", "room_x": -8,
        "instructions": "Đi thang bộ hoặc thang máy lên Tầng 2, cánh trái: Phòng Chụp MRI / CT Scanner / X-Quang.",
    },
    "Xét nghiệm": {
        "floor": 2, "room_name": "Khoa Xét Nghiệm Sinh Hóa", "room_x": 8,
        "instructions": "Đi thang máy lên Tầng 2, cánh phải: Khu lấy mẫu và Xét nghiệm sinh hóa máu/nước tiểu.",
    },
}


# ─────────────────── Tiện ích định dạng history cho triage ─────────────────
def _format_history_for_triage(history: list[dict], message: str) -> str:
    """Chuyển list messages thành đoạn văn bản cho TRIAGE_SYSTEM (vì cần output JSON).
    Chỉ lấy 6 tin nhắn gần nhất (3 lượt trao đổi) để tránh context quá dài.
    """
    lines = []
    for msg in history[-6:]:
        prefix = "Bệnh nhân" if msg["role"] == "user" else "Trợ lý"
        # Cắt bớt nội dung quá dài trong history
        content = msg["content"]
        if len(content) > 400:
            content = content[:400] + "..."
        lines.append(f"{prefix}: {content}")
    lines.append(f"Bệnh nhân: {message}")
    return "\n".join(lines)


# ──────────────────────────── answer() chính ───────────────────────────────
def answer(message: str, history: list[dict] | None = None) -> dict:
    """Xử lý toàn bộ luồng và trả về dict kết quả.

    Args:
        message: Tin nhắn mới nhất của người dùng.
        history: Lịch sử hội thoại — list[{"role": "user"|"assistant", "content": str}].
                 KHÔNG bao gồm message hiện tại.

    Returns dict:
        {
          "type":       "emergency" | "triage" | "clarify" | "procedure" | "other" | "error"
          "text":       str   — văn bản đầy đủ (rỗng khi có stream)
          "stream":     Generator | None — generator streaming (chỉ có khi type="procedure")
          "department": str | None
          "sources":    list[str]
          "location":   dict | None
        }
    """
    history = history or []

    def result(type_: str, text: str = "", department=None,
               sources=None, location=None, stream=None) -> dict:
        return {
            "type":       type_,
            "text":       text,
            "stream":     stream,
            "department": department,
            "sources":    sources or [],
            "location":   location,
        }

    # ── BƯỚC 1: Luật khẩn cấp — nhanh, không tốn API ─────────────────────
    if check_emergency_rules(message):
        loc = DEPARTMENT_MAPPING["Cấp cứu"]
        try:
            log_interaction(message, intent="emergency", department="Cấp cứu", is_emergency=True)
        except Exception:
            pass
        return result("emergency", EMERGENCY_MESSAGE, department="Cấp cứu", location=loc)

    try:
        # ── BƯỚC 2: LLM phân loại ý định + kiểm tra khẩn cấp lần 2 ───────
        route = route_message(message)
        if route["emergency"]:
            loc = DEPARTMENT_MAPPING["Cấp cứu"]
            try:
                log_interaction(message, intent="emergency", department="Cấp cứu", is_emergency=True)
            except Exception:
                pass
            return result("emergency", EMERGENCY_MESSAGE, department="Cấp cứu", location=loc)

        # ── BƯỚC 3a: Hỏi triệu chứng → gợi ý khoa ────────────────────────
        if route["intent"] == "symptom":
            conversation_text = _format_history_for_triage(history, message)
            tri = suggest_department(conversation_text)

            if tri["status"] == "emergency":
                loc = DEPARTMENT_MAPPING["Cấp cứu"]
                try:
                    log_interaction(message, intent="emergency", department="Cấp cứu", is_emergency=True)
                except Exception:
                    pass
                return result("emergency", EMERGENCY_MESSAGE, department="Cấp cứu", location=loc)

            if tri["status"] == "need_more_info":
                q = tri.get("follow_up_question") or "Bạn mô tả rõ hơn triệu chứng giúp mình nhé?"
                try:
                    log_interaction(message, intent="clarify")
                except Exception:
                    pass
                return result("clarify", q)

            dept = tri.get("department") or "Nội tổng quát"
            loc  = DEPARTMENT_MAPPING.get(dept, DEPARTMENT_MAPPING["Nội tổng quát"])
            text = (
                f"Bạn nên đăng ký khám **khoa {dept}**.\n\n"
                f"{tri.get('reason', '')}\n\n"
                f"📍 **Vị trí phòng khám:** Tầng {loc['floor']} — {loc['room_name']}.\n"
                f"👉 **Chỉ dẫn:** {loc['instructions']}\n\n"
                "_Đây chỉ là gợi ý hướng dẫn đăng ký khám, không phải chẩn đoán "
                "và không thay thế bác sĩ._"
            )
            try:
                log_interaction(message, intent="symptom", department=dept)
            except Exception:
                pass
            return result("triage", text, department=dept, location=loc)

        # ── BƯỚC 3b: Hỏi quy trình/BHYT → RAG + streaming ────────────────
        if route["intent"] == "procedure":
            chunks  = get_retriever().search(message)
            sources = sorted({c["source"] for c in chunks})
            # Chỉ truyền tối đa 8 tin nhắn gần nhất để tránh context quá dài
            rag_history = history[-8:]
            stream_gen  = answer_procedure_stream(message, chunks, history=rag_history)
            try:
                log_interaction(message, intent="procedure")
            except Exception:
                pass
            return result("procedure", sources=sources, stream=stream_gen)

        # ── BƯỚC 4: Intent khác ───────────────────────────────────────────
        try:
            log_interaction(message, intent="other")
        except Exception:
            pass
        return result(
            "other",
            "Mình chỉ hỗ trợ chọn khoa khám và giải đáp quy trình, "
            "giấy tờ, bảo hiểm khi đi khám nhé 😊",
        )

    except Exception as error:
        print("LỖI THẬT:", repr(error))
        return result(
            "error",
            f"Xin lỗi, hệ thống đang gặp sự cố ({type(error).__name__}). "
            "Nếu khẩn cấp, hãy liên hệ trực tiếp nhân viên bệnh viện.",
        )


# ──────────────────────── Chạy thử terminal ────────────────────────────────
if __name__ == "__main__":
    print("Trợ lý tiếp đón ATus (gõ 'thoat' để dừng)\n")
    chat_history: list[dict] = []

    while True:
        user_input = input("Bạn: ").strip()
        if user_input.lower() == "thoat":
            break

        reply = answer(user_input, history=chat_history)
        chat_history.append({"role": "user", "content": user_input})

        if reply.get("stream"):
            print(f"\n[{reply['type']}] ", end="", flush=True)
            full = ""
            for chunk in reply["stream"]:
                print(chunk, end="", flush=True)
                full += chunk
            print()
            chat_history.append({"role": "assistant", "content": full})
        else:
            print(f"\n[{reply['type']}] {reply['text']}")
            chat_history.append({"role": "assistant", "content": reply["text"]})

        if reply.get("sources"):
            print("Nguồn:", " | ".join(reply["sources"]))
        print()

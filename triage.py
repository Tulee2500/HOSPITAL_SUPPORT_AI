"""BƯỚC 2 và 3 — Phân loại tin nhắn, gợi ý khoa, trả lời quy trình (streaming).

Hàm mới so với phiên bản cũ:
  answer_procedure_stream(question, chunks, history) → Generator[str]
  answer_procedure(question, chunks, history)        → str   (giữ lại để test)
"""
from __future__ import annotations

from typing import Generator

from llm import ask_json, ask_llm, stream_llm

DEPARTMENTS = [
    "Cấp cứu", "Nội tổng quát", "Ngoại tổng quát", "Mắt", "Tai mũi họng",
    "Răng hàm mặt", "Da liễu", "Sản phụ khoa", "Nhi khoa",
    "Chẩn đoán hình ảnh", "Xét nghiệm", "Tim mạch", "Hô hấp", "Tiêu hóa",
    "Thần kinh", "Cơ xương khớp",
]

# ──────────────────────────── System Prompts ───────────────────────────────
ROUTER_SYSTEM = """Bạn là bộ phân loại tin nhắn cho trợ lý tiếp đón bệnh viện tại Việt Nam.
Chỉ trả về DUY NHẤT một đối tượng JSON, không thêm chữ nào khác:
{"intent": "symptom" | "procedure" | "other", "emergency": true | false}

- "symptom"  : người dùng mô tả triệu chứng/vấn đề sức khỏe và cần biết nên khám khoa nào.
- "procedure": hỏi về quy trình khám, giấy tờ, bảo hiểm y tế, giờ làm việc, đặt lịch, chi phí.
- "other"    : nội dung khác.
- emergency = true nếu có dấu hiệu có thể đe dọa tính mạng (đau ngực dữ dội, khó thở,
  méo miệng hoặc yếu liệt một bên, mất ý thức, co giật, chảy máu nhiều, ý định tự tử...).
  Nếu phân vân, hãy chọn true."""

TRIAGE_SYSTEM = f"""Bạn là trợ lý tiếp đón của bệnh viện, giúp bệnh nhân chọn khoa khám.
Danh sách khoa hợp lệ: {", ".join(DEPARTMENTS)}.
Bạn KHÔNG chẩn đoán bệnh, KHÔNG nói tên bệnh, KHÔNG gợi ý thuốc.
Bên dưới là lịch sử hội thoại (nếu có) và tin nhắn mới nhất của bệnh nhân.
Chỉ trả về DUY NHẤT một đối tượng JSON:
{{"status": "ok" | "need_more_info" | "emergency",
  "department": "<đúng một khoa trong danh sách, hoặc null>",
  "reason": "<1-2 câu tiếng Việt giải thích vì sao nên khám khoa này, không chẩn đoán>",
  "follow_up_question": "<1 câu hỏi làm rõ nếu cần, hoặc null>"}}
Quy tắc:
- Thông tin quá ít → status = "need_more_info" và hỏi 1 câu làm rõ.
- Có bất kỳ dấu hiệu nguy hiểm → status = "emergency".
- Không chắc nên chọn khoa nào → chọn "Nội tổng quát"."""

RAG_SYSTEM = """Bạn là trợ lý tiếp đón bệnh viện ATus. Chỉ trả lời dựa trên phần TÀI LIỆU được cung cấp.
Nếu tài liệu không có thông tin để trả lời, hãy nói: "Mình chưa có thông tin này, bạn vui lòng
liên hệ quầy tiếp đón hoặc tổng đài của bệnh viện." TUYỆT ĐỐI không bịa giá tiền, giờ làm việc,
con số. Trả lời ngắn gọn, tiếng Việt, dùng gạch đầu dòng khi liệt kê.
Nếu có lịch sử hội thoại bên trên, hãy trả lời phù hợp với ngữ cảnh câu hỏi trước đó."""

_NO_INFO_MSG = (
    "Mình chưa có thông tin này, bạn vui lòng liên hệ quầy tiếp đón "
    "hoặc tổng đài **024.7777.9999** của bệnh viện nhé."
)


# ────────────────────────── Route message ──────────────────────────────────
def route_message(message: str) -> dict:
    """Phân loại: symptom / procedure / other, và có khẩn cấp không."""
    result = ask_json(ROUTER_SYSTEM, message, max_tokens=100)
    if not result:
        return {"intent": "other", "emergency": True}   # an toàn: báo khẩn nếu không rõ
    return {
        "intent":    result.get("intent", "other"),
        "emergency": bool(result.get("emergency", True)),
    }


# ──────────────────────── Suggest department ───────────────────────────────
def suggest_department(conversation: str) -> dict:
    """Gợi ý khoa dựa trên đoạn hội thoại đã được định dạng thành văn bản.
    Trả về dict có key 'status': 'ok' | 'need_more_info' | 'emergency'.
    """
    result = ask_json(TRIAGE_SYSTEM, conversation, max_tokens=300)
    if not result:
        return {
            "status": "need_more_info", "department": None, "reason": "",
            "follow_up_question": "Bạn có thể mô tả rõ hơn triệu chứng và thời gian bị không?",
        }
    # Mô hình trả khoa không có trong danh sách → fallback
    if result.get("status") == "ok" and result.get("department") not in DEPARTMENTS:
        result["department"] = "Nội tổng quát"
    return result


# ──────────────────── Procedure answer — blocking ──────────────────────────
def answer_procedure(
    question: str,
    retrieved_chunks: list,
    history: list[dict] | None = None,
) -> str:
    """Trả lời quy trình/thủ tục — phiên bản blocking (dùng để test)."""
    if not retrieved_chunks:
        return _NO_INFO_MSG
    context = "\n\n---\n\n".join(c["text"] for c in retrieved_chunks)
    user_msg = f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {question}"
    return ask_llm(RAG_SYSTEM, user_msg, max_tokens=600, history=history or [])


# ─────────────────── Procedure answer — streaming ──────────────────────────
def answer_procedure_stream(
    question: str,
    retrieved_chunks: list,
    history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """Trả lời quy trình/thủ tục — phiên bản streaming.
    Yield từng đoạn văn bản khi LLM tạo ra. Dùng với st.write_stream().
    """
    if not retrieved_chunks:
        yield _NO_INFO_MSG
        return
    context = "\n\n---\n\n".join(c["text"] for c in retrieved_chunks)
    user_msg = f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {question}"
    yield from stream_llm(RAG_SYSTEM, user_msg, max_tokens=600, history=history or [])

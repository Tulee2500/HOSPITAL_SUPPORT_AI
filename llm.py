"""Chỗ DUY NHẤT gọi mô hình AI — hỗ trợ multi-turn history và streaming.

Đổi nhà cung cấp bằng cách sửa LLM_PROVIDER trong file .env, các file khác không đổi.

Các hàm public:
  ask_llm(system, user, max_tokens, retries, history)   → str          (blocking)
  stream_llm(system, user, max_tokens, history)          → Generator    (streaming)
  ask_json(system, user, max_tokens)                     → dict | None  (blocking, parse JSON)
"""
from __future__ import annotations

import json
import os
import time
from typing import Generator

from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()   # "gemini" hoặc "anthropic"
MODEL    = os.getenv("LLM_MODEL", "gemini-2.5-flash" if PROVIDER == "gemini" else "claude-haiku-5-5")
_client  = None


# ─────────────────────────── Khởi tạo client ───────────────────────────────
def _get_client():
    global _client
    if _client is None:
        if PROVIDER == "gemini":
            from google import genai
            _client = genai.Client()          # tự đọc GEMINI_API_KEY từ môi trường
        else:
            import anthropic
            _client = anthropic.Anthropic()   # tự đọc ANTHROPIC_API_KEY
    return _client


# ─────────────────────── Chuyển đổi định dạng history ──────────────────────
def _to_gemini_contents(history: list[dict], user_message: str) -> list:
    """Chuyển [{role, content}] + tin nhắn mới → định dạng Gemini contents."""
    contents = []
    for msg in history:
        # Gemini dùng "model" thay cho "assistant"
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


def _to_anthropic_messages(history: list[dict], user_message: str) -> list:
    """Chuyển history + tin nhắn mới → định dạng Anthropic messages."""
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})
    return messages


# ──────────────────────────── ask_llm (blocking) ───────────────────────────
def ask_llm(
    system: str,
    user: str,
    max_tokens: int = 600,
    retries: int = 4,
    history: list[dict] | None = None,
) -> str:
    """Gửi câu hỏi (kèm history tuỳ chọn) cho LLM, nhận về chuỗi văn bản.
    history: list[{"role": "user"|"assistant", "content": str}] — tin nhắn trước đó.
    Tự thử lại khi máy chủ quá tải (429 / 503).
    """
    history = history or []
    for attempt in range(retries):
        try:
            client = _get_client()
            if PROVIDER == "gemini":
                from google.genai import types
                contents = _to_gemini_contents(history, user)
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        # Gemini tính cả "thinking tokens" vào giới hạn → đặt >= 2048
                        max_output_tokens=max(max_tokens, 2048),
                    ),
                )
                return resp.text or ""
            # Anthropic
            messages = _to_anthropic_messages(history, user)
            resp = _get_client().messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return resp.content[0].text
        except Exception as error:
            temporary = any(k in str(error) for k in ("503", "429", "UNAVAILABLE", "overloaded"))
            if temporary and attempt < retries - 1:
                wait = 2 ** (attempt + 1)   # 2 s, 4 s, 8 s
                print(f"Máy chủ bận, thử lại sau {wait}s (lần {attempt + 1}/{retries - 1})...")
                time.sleep(wait)
                continue
            raise


# ───────────────────────── stream_llm (streaming) ──────────────────────────
def stream_llm(
    system: str,
    user: str,
    max_tokens: int = 600,
    history: list[dict] | None = None,
) -> Generator[str, None, None]:
    """Phiên bản streaming của ask_llm — yield từng đoạn văn bản khi LLM tạo ra.
    Dùng với st.write_stream() trong Streamlit.
    """
    history = history or []
    client  = _get_client()

    try:
        if PROVIDER == "gemini":
            from google.genai import types
            contents = _to_gemini_contents(history, user)
            for chunk in client.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max(max_tokens, 2048),
                ),
            ):
                if chunk.text:
                    yield chunk.text
        else:
            # Anthropic streaming
            messages = _to_anthropic_messages(history, user)
            with client.messages.stream(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            ) as stream:
                yield from stream.text_stream

    except Exception as error:
        # Không để lỗi crash toàn bộ stream — yield thông báo lỗi inline
        yield f"\n\n_(Lỗi kết nối: {type(error).__name__}. Vui lòng thử lại hoặc liên hệ quầy tiếp đón.)_"


# ─────────────────────────── ask_json (helper) ─────────────────────────────
def ask_json(system: str, user: str, max_tokens: int = 400) -> dict | None:
    """Như ask_llm nhưng ép kết quả thành dict JSON. Trả về None nếu sai định dạng.
    Không nhận history vì các lời gọi JSON đều là single-turn phân loại.
    """
    text = ask_llm(system, user, max_tokens)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start: end + 1])
    except json.JSONDecodeError:
        return None

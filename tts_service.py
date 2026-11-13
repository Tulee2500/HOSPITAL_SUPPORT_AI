"""Dịch vụ Phát Âm Thanh Gọi Số & Tổng Hợp Giọng Nói Y Tế (Hospital Voice & Chime TTS).

Tuân thủ kiến trúc phân tầng âm thanh sảnh chờ:
1. Hoạt động 100% Cục Bộ / Offline (Zero Internet Dependency): Không phụ thuộc cloud API.
2. Âm thanh chuông báo chuẩn y tế (Hospital Chime 'Ding-Dong'): Tự động tổng hợp sóng âm dạng WAV 2 cung bậc (D5 - A4).
3. Hỗ trợ đa tầng phát âm:
   - Cấp 1: Web Speech API trên màn hình TV Callboard (giọng đọc mượt mà, đồng bộ lập tức).
   - Cấp 2: Server-side Offline TTS qua pyttsx3 (SAPI5 / eSpeak) sinh file audio phục vụ phát loa sảnh tập trung.
4. Mẫu câu gọi số chuẩn hóa Bộ Y Tế:
   - Khám thường: "Xin mời bệnh nhân số [Mã vé], [Tên], vào [Phòng khám], [Tầng]."
   - Gọi lại: "Mời bệnh nhân số [Mã vé], [Tên], khẩn trương vào [Phòng khám]."
   - Cấp cứu khẩn cấp: "Cảnh báo cấp cứu! Yêu cầu kíp trực chuẩn bị đón bệnh nhân số [Mã vé] tại Khoa Cấp Cứu Tầng 1."
"""
from __future__ import annotations

import io
import math
import struct
import wave
import base64
import os
from typing import Optional

# Thử import pyttsx3 cho server-side offline TTS
HAS_PYTTSX3 = False
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except Exception:
    HAS_PYTTSX3 = False


def generate_hospital_chime_wav() -> bytes:
    """Tạo âm thanh chuông báo sảnh chờ bệnh viện chuẩn 2 âm (Ding-Dong) bằng thuật toán tổng hợp âm học."""
    sample_rate = 22050
    buf = io.BytesIO()
    
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)        # Mono
        wav.setsampwidth(2)        # 16-bit
        wav.setframerate(sample_rate)
        
        # Tone 1: 'Ding' - Nốt Re cao (D5 = 587.33 Hz) trong 0.35s
        tone1_samples = int(sample_rate * 0.35)
        freq1 = 587.33
        for i in range(tone1_samples):
            # Biên độ suy giảm theo hàm mũ e^(-t/tau)
            decay = math.exp(-i / (sample_rate * 0.18))
            # Sóng sin kèm hài âm nhẹ cho âm thanh ấm
            val = (math.sin(2 * math.pi * freq1 * i / sample_rate) * 0.85 +
                   math.sin(2 * math.pi * (freq1 * 2) * i / sample_rate) * 0.15)
            sample = int(val * decay * 22000)
            wav.writeframes(struct.pack('<h', max(-32767, min(32767, sample))))

        # Khoảng lặng ngắn 0.05s
        silence_samples = int(sample_rate * 0.05)
        for _ in range(silence_samples):
            wav.writeframes(struct.pack('<h', 0))

        # Tone 2: 'Dong' - Nốt La (A4 = 440.00 Hz) trong 0.55s
        tone2_samples = int(sample_rate * 0.55)
        freq2 = 440.00
        for i in range(tone2_samples):
            decay = math.exp(-i / (sample_rate * 0.28))
            val = (math.sin(2 * math.pi * freq2 * i / sample_rate) * 0.85 +
                   math.sin(2 * math.pi * (freq2 * 2) * i / sample_rate) * 0.15)
            sample = int(val * decay * 24000)
            wav.writeframes(struct.pack('<h', max(-32767, min(32767, sample))))

    buf.seek(0)
    return buf.getvalue()


_CHIME_B64_CACHE: Optional[str] = None

def get_chime_base64() -> str:
    """Lấy chuỗi base64 của âm chuông để nhúng phát trực tiếp trong trình duyệt Kiosk / Callboard."""
    global _CHIME_B64_CACHE
    if _CHIME_B64_CACHE is None:
        wav_bytes = generate_hospital_chime_wav()
        _CHIME_B64_CACHE = base64.b64encode(wav_bytes).decode('utf-8')
    return _CHIME_B64_CACHE


def format_call_speech_text(
    ticket_number: str,
    patient_name: str,
    room_name: str,
    floor: int,
    is_recall: bool = False,
    is_emergency: bool = False
) -> str:
    """Tạo câu đọc gọi số chuẩn y tế cho sảnh chờ."""
    # Tách mã phòng và đọc từng chữ số rõ ràng (ví dụ NOI01-021 -> N O I 0 1, số 21)
    if is_emergency:
        return f"Cảnh báo cấp cứu! Yêu cầu kíp trực tiếp nhận bệnh nhân số {ticket_number}, {patient_name}, tại Khoa Cấp Cứu, Tầng 1 ngay lập tức."
    
    if is_recall:
        return f"Xin thông báo lần hai: Mời bệnh nhân số {ticket_number}, {patient_name}, khẩn trương vào phòng {room_name}, Tầng {floor} để khám bệnh."
    
    return f"Xin mời bệnh nhân số {ticket_number}, {patient_name}, vào phòng {room_name}, Tầng {floor}."


def synthesize_speech_offline(text: str, output_path: str | None = None) -> bytes | None:
    """Tổng hợp giọng nói offline qua engine pyttsx3 (SAPI5/eSpeak)."""
    if not HAS_PYTTSX3:
        return None
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)  # Tốc độ đọc vừa phải chuẩn y tế
        engine.setProperty('volume', 1.0)

        # Ưu tiên tìm giọng đọc tiếng Việt nếu có cài trên OS
        voices = engine.getProperty('voices')
        for v in voices:
            if "vietnam" in v.name.lower() or "vi-vn" in v.id.lower() or "an" in v.name.lower():
                engine.setProperty('voice', v.id)
                break

        temp_file = output_path or "temp_call_audio.wav"
        engine.save_to_file(text, temp_file)
        engine.runAndWait()

        if os.path.exists(temp_file):
            with open(temp_file, "rb") as f:
                data = f.read()
            if not output_path:
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return data
    except Exception as e:
        print(f"Lỗi synthesize_speech_offline: {e}")
        return None
    return None

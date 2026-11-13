"""Màn Hình Sảnh Chờ & Gọi Số Loa Tập Trung (Hospital Public Callboard & Voice Announcement).

Thiết kế tối ưu cho màn hình TV lớn (55 - 75 inch) tại sảnh tiếp đón Bệnh Viện ATUS:
1. Độ tương phản cao chuẩn y tế, chữ số to rõ có thể quan sát từ khoảng cách 15 mét.
2. Tự động phát âm thanh chuông báo (Chime 2 âm 'Ding-Dong') kèm giọng đọc tiếng Việt khi bác sĩ bấm gọi.
3. Hoạt động 100% Cục Bộ / Offline (Zero Internet Dependency): Tự tổng hợp âm học và dự phòng SAPI5.
4. Lưới hiển thị đa khoa phòng thời gian thực, tự động đồng bộ theo chu kỳ 3 giây.
5. Dải băng thông tin chạy ngang (Ticker Marquee) thông báo chỉ dẫn y tế.

Khởi chạy độc lập:
    streamlit run app_callboard.py --server.port 8503
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
import json

import queue_service
import tts_service

st.set_page_config(
    page_title="Bệnh Viện ATUS - Bảng Gọi Số Sảnh Chờ",
    page_icon="📢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════════════════════════════
# TÙY BIẾN CSS FULLSCREEN TV DISPLAY
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* Ẩn header mặc định và padding */
    header[data-testid="stHeader"] { display: none !important; }
    .main .block-container {
        padding: 0.8rem 1.4rem !important;
        max-width: 100% !important;
        background-color: #0b192c;
        color: #ffffff;
    }
    body { background-color: #0b192c; }

    /* Thanh tiêu đề sảnh chờ */
    .tv-header {
        display: flex; justify-content: space-between; align-items: center;
        background: linear-gradient(135deg, #003a70 0%, #008f88 100%);
        border-radius: 12px; padding: 12px 24px; margin-bottom: 14px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); border: 1.5px solid #00a896;
    }
    .tv-title { font-size: 1.5rem; font-weight: 900; letter-spacing: 0.8px; color: #ffffff; margin: 0; }
    .tv-clock { font-size: 1.3rem; font-weight: 800; color: #64ffda; letter-spacing: 1px; }

    /* Khung Lượt Gọi Mới Nhất (Hero Callout Box) */
    .hero-call-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 3px solid #008f88; border-radius: 16px; padding: 18px 24px;
        margin-bottom: 16px; box-shadow: 0 8px 32px rgba(0, 143, 136, 0.35);
        display: flex; justify-content: space-between; align-items: center;
        animation: pulseBorder 2s infinite;
    }
    .hero-call-box.emergency {
        border-color: #ef4444 !important;
        box-shadow: 0 8px 32px rgba(239, 68, 68, 0.5) !important;
    }
    @keyframes pulseBorder {
        0% { box-shadow: 0 0 10px rgba(0, 143, 136, 0.4); }
        50% { box-shadow: 0 0 25px rgba(0, 143, 136, 0.8); }
        100% { box-shadow: 0 0 10px rgba(0, 143, 136, 0.4); }
    }
    .hero-label { font-size: 1.05rem; font-weight: 800; color: #00e5ff; letter-spacing: 1px; text-transform: uppercase; }
    .hero-number { font-size: 4rem; font-weight: 900; color: #ffffff; letter-spacing: 2px; text-shadow: 0 2px 10px rgba(0,229,255,0.6); }
    .hero-patient { font-size: 1.8rem; font-weight: 800; color: #f1f5f9; margin-top: 2px; }
    .hero-room { font-size: 2.2rem; font-weight: 900; color: #ffd166; text-align: right; }
    .hero-floor { font-size: 1.25rem; font-weight: 700; color: #94a3b8; text-align: right; }

    /* Thẻ phòng khám dạng lưới */
    .room-grid-card {
        background: #1e293b; border: 1.5px solid #334155; border-radius: 12px;
        padding: 12px 14px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        transition: border-color 0.2s;
    }
    .room-grid-card.calling {
        border-color: #00e5ff !important; background: #0f2744 !important;
    }
    .room-name-bar {
        display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1px solid #334155; padding-bottom: 6px; margin-bottom: 8px;
    }
    .room-badge-num {
        background: #008f88; color: #ffffff; font-size: 1.6rem; font-weight: 900;
        padding: 4px 12px; border-radius: 8px; text-align: center; letter-spacing: 1px;
    }
    .next-badge-num {
        background: #334155; color: #cbd5e1; font-size: 1.2rem; font-weight: 700;
        padding: 3px 8px; border-radius: 6px; text-align: center;
    }

    /* Dải tin chạy ngang (Marquee) */
    .tv-marquee {
        background: #0f172a; border: 1px solid #1e293b; border-radius: 8px;
        padding: 8px 16px; margin-top: 14px; overflow: hidden; white-space: nowrap;
        color: #94a3b8; font-size: 0.95rem; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# QUẢN LÝ SESSION VÀ TỰ ĐỘNG PHÁT ÂM THANH KHI CÓ LƯỢT GỌI MỚI
# ═══════════════════════════════════════════════════════════════════════════
if "last_played_ticket_id" not in st.session_state:
    st.session_state.last_played_ticket_id = None
if "selected_tv_floor" not in st.session_state:
    st.session_state.selected_tv_floor = None  # None = Tất cả các tầng

# Thanh điều khiển tầng & âm thanh
c_t1, c_t2, c_t3 = st.columns([55, 25, 20])
with c_t1:
    floor_opts = ["Tất cả các tầng", "Tầng 1 (Tiếp đón & Cấp cứu)", "Tầng 2 (Chuyên khoa ngoại trú)", "Tầng 3 (Nội trú & Mổ)"]
    sel_f_str = st.selectbox("Chọn tầng sảnh chờ:", options=floor_opts, index=0, label_visibility="collapsed")
    f_map = {
        "Tất cả các tầng": None,
        "Tầng 1 (Tiếp đón & Cấp cứu)": 1,
        "Tầng 2 (Chuyên khoa ngoại trú)": 2,
        "Tầng 3 (Nội trú & Mổ)": 3
    }
    st.session_state.selected_tv_floor = f_map.get(sel_f_str)

with c_t2:
    enable_audio = st.checkbox("🔊 Bật Loa Gọi Số Sảnh Chờ", value=True)

with c_t3:
    btn_test_sound = st.button("🔔 Thử Chuông Loa Sảnh", use_container_width=True)

# Lấy dữ liệu Callboard từ database
cb_data = queue_service.get_callboard_data(floor=st.session_state.selected_tv_floor)
latest_call = cb_data["latest_calling"]

# ═══════════════════════════════════════════════════════════════════════════
# HEADER SẢNH CHỜ
# ═══════════════════════════════════════════════════════════════════════════
floor_text = f"TẦNG {st.session_state.selected_tv_floor}" if st.session_state.selected_tv_floor else "TOÀN VIỆN"
st.markdown(f"""
<div class="tv-header">
    <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:28px;">🏥</span>
        <div>
            <h1 class="tv-title">BỆNH VIỆN ĐA KHOA QUỐC TẾ ATUS</h1>
            <div style="font-size:0.85rem;color:#e0f2fe;font-weight:600;">HỆ THỐNG GỌI SỐ SẢNH CHỜ TỰ ĐỘNG · {floor_text}</div>
        </div>
    </div>
    <div class="tv-clock">
        ⏰ {cb_data['timestamp']}
    </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# LƯỢT GỌI MỚI NHẤT (HERO CALLOUT BANNER)
# ═══════════════════════════════════════════════════════════════════════════
should_play_audio = False
audio_speech_text = ""

if latest_call:
    is_er = latest_call["is_emergency"]
    er_class = " emergency" if is_er else ""
    er_badge = "🚨 CẤP CỨU KHẨN CẤP" if is_er else "🔔 ĐANG GỌI VÀO PHÒNG"

    st.markdown(f"""
    <div class="hero-call-box{er_class}">
        <div>
            <div class="hero-label">{er_badge}</div>
            <div class="hero-number">{latest_call['ticket_number']}</div>
            <div class="hero-patient">👤 {latest_call['patient_name_masked']}</div>
        </div>
        <div>
            <div class="hero-room">{latest_call['room_name']} ({latest_call['room_number']})</div>
            <div class="hero-floor">📍 TẦNG {latest_call['floor']} · Bác sĩ: {latest_call['doctor_name']}</div>
            <div style="font-size:0.95rem;color:#64ffda;text-align:right;margin-top:4px;">Thời gian gọi: {latest_call['called_at_str']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Kiểm tra xem lượt gọi này đã được phát âm thanh chưa
    if latest_call["ticket_id"] != st.session_state.last_played_ticket_id:
        st.session_state.last_played_ticket_id = latest_call["ticket_id"]
        should_play_audio = True
        audio_speech_text = tts_service.format_call_speech_text(
            ticket_number=latest_call["ticket_number"],
            patient_name=latest_call["patient_name_masked"],
            room_name=f"{latest_call['room_name']} số {latest_call['room_number']}",
            floor=latest_call["floor"],
            is_emergency=is_er
        )
else:
    st.markdown("""
    <div style="background:#1e293b;border:2px dashed #334155;border-radius:14px;padding:22px;text-align:center;margin-bottom:16px;">
        <span style="font-size:1.15rem;color:#94a3b8;font-weight:700;">🟢 CÁC PHÒNG KHÁM ĐANG SẴN SÀNG TIẾP ĐÓN BỆNH NHÂN</span>
    </div>
    """, unsafe_allow_html=True)

if btn_test_sound:
    should_play_audio = True
    audio_speech_text = "Xin mời bệnh nhân số N O I 0 1, không hai mốt, Nguyễn Văn An, vào phòng khám Nội tổng quát 1, Tầng 1."

# ═══════════════════════════════════════════════════════════════════════════
# PHÁT ÂM THANH CHUÔNG VÀ GIỌNG ĐỌC QUA WEB SPEECH API & OFFLINE CHIME
# ═══════════════════════════════════════════════════════════════════════════
if enable_audio and should_play_audio and audio_speech_text:
    chime_b64 = tts_service.get_chime_base64()
    escaped_text = json.dumps(audio_speech_text, ensure_ascii=False)

    components.html(f"""
    <script>
    (function() {{
        // 1. Phát âm thanh chuông 2 âm Ding-Dong (WAV Base64)
        const chimeAudio = new Audio("data:audio/wav;base64,{chime_b64}");
        chimeAudio.volume = 1.0;
        
        chimeAudio.onended = function() {{
            // 2. Phát giọng đọc tiếng Việt qua Web Speech API
            if ('speechSynthesis' in window) {{
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance({escaped_text});
                utter.lang = 'vi-VN';
                utter.rate = 0.95; // Tốc độ vừa phải cho sảnh chờ
                utter.pitch = 1.0;
                
                // Tìm giọng đọc tiếng Việt nếu có
                const voices = window.speechSynthesis.getVoices();
                for (let i = 0; i < voices.length; i++) {{
                    if (voices[i].lang.includes('vi') || voices[i].name.toLowerCase().includes('vietnam')) {{
                        utter.voice = voices[i];
                        break;
                    }}
                }}
                window.speechSynthesis.speak(utter);
            }}
        }};

        chimeAudio.play().catch(e => console.log('Audio autoplay prevented:', e));
    }})();
    </script>
    """, height=0)

# ═══════════════════════════════════════════════════════════════════════════
# LƯỚI BẢNG GỌI SỐ CÁC PHÒNG KHÁM (ROOMS MATRIX)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("<h3 style='color:#00e5ff;font-size:1.15rem;margin:10px 0 8px 0;letter-spacing:0.5px;'>📋 TÌNH HÌNH PHỤC VỤ CÁC PHÒNG KHÁM</h3>", unsafe_allow_html=True)

# Lọc chỉ lấy các phòng có bệnh nhân hoặc đang hoạt động
active_rooms = [r for r in cb_data["rooms"] if r["current_ticket"] != "---" or r["waiting_count"] > 0]
if not active_rooms:
    active_rooms = cb_data["rooms"][:12]  # Lấy 12 phòng mẫu đầu tiên nếu sáng sớm chưa có số

cols_per_row = 4
rows_count = (len(active_rooms) + cols_per_row - 1) // cols_per_row

for r_idx in range(rows_count):
    row_rooms = active_rooms[r_idx * cols_per_row : (r_idx + 1) * cols_per_row]
    cols = st.columns(cols_per_row)
    for c_idx, room in enumerate(row_rooms):
        with cols[c_idx]:
            is_calling_room = (room["current_status"] == "calling")
            card_class = "room-grid-card calling" if is_calling_room else "room-grid-card"
            status_text = "🔔 ĐANG GỌI" if is_calling_room else ("🩺 ĐANG KHÁM" if room["current_status"] == "in_progress" else "⏳ SẴN SÀNG")
            status_color = "#00e5ff" if is_calling_room else ("#4ade80" if room["current_status"] == "in_progress" else "#94a3b8")

            st.markdown(f"""
            <div class="{card_class}">
                <div class="room-name-bar">
                    <b style="font-size:0.95rem;color:#ffffff;">{room['room_name']}</b>
                    <span style="font-size:0.75rem;font-weight:700;color:{status_color};">{status_text}</span>
                </div>
                <div style="font-size:0.8rem;color:#94a3b8;margin-bottom:8px;">
                    Mã: <b>{room['room_number']}</b> · Tầng <b>{room['floor']}</b> · BS: <b>{room['doctor_name']}</b>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-size:0.8rem;color:#94a3b8;">Đang phục vụ:</span>
                    <span class="room-badge-num">{room['current_ticket']}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:0.78rem;color:#64748b;">Số chuẩn bị: <b style="color:#ffd166;">{room['next_ticket']}</b></span>
                    <span style="font-size:0.78rem;color:#64748b;">Chờ: <b style="color:#00e5ff;">{room['waiting_count']} người</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# DẢI TIN TỨC CHẠY NGANG (TICKER MARQUEE)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="tv-marquee">
    <marquee scrollamount="5" behavior="scroll" direction="left">
        🏥 <b>Bệnh Viện Đa Khoa Quốc Tế ATUS</b> kính chúc quý bệnh nhân mau chóng hồi phục sức khỏe! &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        📞 <b>Hotline Cấp Cứu 24/7:</b> 115 - Tổng Đài Bệnh Viện: 024.7777.9999 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        💳 Người bệnh đăng ký khám BHYT vui lòng xuất trình <b>CCCD gắn chip</b> hoặc ứng dụng <b>VssID</b> tại Quầy tiếp đón Tầng 1. &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        🧭 Quý khách có thể quét mã QR trên Phiếu Khám Bệnh để theo dõi lộ trình di chuyển 3D trên điện thoại cá nhân.
    </marquee>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# TỰ ĐỘNG LÀM MỚI MÀN HÌNH MỖI 3.5 GIÂY (AUTO-REFRESH LOOP)
# ═══════════════════════════════════════════════════════════════════════════
components.html("""
<script>
setTimeout(function() {
    window.parent.location.reload();
}, 3500);
</script>
""", height=0)

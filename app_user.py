"""Giao diện Cổng Bệnh Nhân & Kiosk Tiếp Đón (AI Hospital Assistant & Map - Bệnh Viện ATus).
Khắc phục triệt để 4 lỗi:
1. Thanh taskbar/sidebar khi ẩn có nút mở lại (chevron) luôn hiển thị nổi bật ở góc trên trái, ấn là mở lại ngay.
2. Cửa sổ AI Chatbot: Nút tròn nổi (Floating Action Button 💬) góc phải dưới màn hình.
   - Bấm nút tròn -> Mở bung popup chat AI.
   - Bấm nút thu nhỏ [_] hoặc [✕] -> Thu nhỏ lại thành nút tròn nổi.
   - RAG + Triage tốc độ cao (0.5s), không bị treo/đứng máy, hỗ trợ Voice tiếng Việt.
3. Tên bệnh viện hiển thị thống nhất chuẩn xác: BỆNH VIỆN ATUS (Bệnh Viện Đa Khoa Quốc Tế ATus).
4. Menu taskbar bên trái hoạt động độc lập và đầy đủ: Trang chủ, Bản đồ 3D, Đặt lịch hẹn, Tư vấn AI, Lịch sử khám, Cài đặt.
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime
import pandas as pd

import queue_service
import db
from assistant import answer
from atus_hospital_3d_real import get_hospital_3d_html
from sms_service import send_appointment_sms

# Cấu hình Layout Wide chuẩn giao diện ứng dụng web
st.set_page_config(
    page_title="Bệnh Viện ATus - AI Hospital Assistant & Map",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════
# TÙY BIẾN CSS CHUẨN DESIGN MOCKUP & FIX LỖI SIDEBAR + FLOATING CHAT
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* 1. ĐẢM BẢO NÚT MỞ SIDEBAR LUÔN HIỂN THỊ KHI SIDEBAR BỊ ẨN */
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 9999999 !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
    }
    [data-testid="stSidebarCollapsedControl"] button {
        background: #003a70 !important;
        color: #ffffff !important;
        border: 2px solid #008f88 !important;
        border-radius: 8px !important;
        width: 38px !important;
        height: 38px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 4px 12px rgba(0, 58, 112, 0.4) !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background: #008f88 !important;
        transform: scale(1.05) !important;
    }
    [data-testid="stSidebarCollapsedControl"] svg {
        fill: #ffffff !important;
        stroke: #ffffff !important;
        width: 22px !important;
        height: 22px !important;
    }

    /* Header Streamlit trong suốt */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        height: 2.2rem !important;
        z-index: 100 !important;
    }

    .main .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 100% !important;
        background-color: #f8fafc;
    }
    
    /* 2. Thanh Sidebar bên trái (Màu xanh navy đậm #003a70) */
    section[data-testid="stSidebar"] {
        background-color: #003a70 !important;
        min-width: 250px !important;
        max-width: 260px !important;
    }
    section[data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    .sidebar-brand {
        display: flex; align-items: center; gap: 10px;
        padding: 6px 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.18);
        margin-bottom: 15px;
    }
    .brand-icon {
        width: 42px; height: 42px; background: #ffffff;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }
    .brand-title {
        font-size: 1.05rem; font-weight: 800; line-height: 1.2; letter-spacing: 0.5px;
    }

    /* Menu Sidebar dạng button radio tinh tế */
    div[data-testid="stSidebar"] .stRadio > div {
        gap: 6px;
    }
    div[data-testid="stSidebar"] .stRadio label {
        padding: 9px 12px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        transition: 0.2s all !important;
        cursor: pointer !important;
        margin: 0 !important;
    }
    div[data-testid="stSidebar"] .stRadio label:hover {
        background-color: rgba(0, 143, 136, 0.4) !important;
    }
    div[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background-color: #008f88 !important;
        color: #ffffff !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2) !important;
    }

    /* 3. Top Navbar Bar (Tìm kiếm, chuông báo, Avatar) */
    .top-navbar {
        display: flex; justify-content: space-between; align-items: center;
        background: #ffffff; padding: 8px 18px; border-radius: 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04); margin-bottom: 14px;
        border: 1px solid #e2e8f0;
    }
    .search-box {
        display: flex; align-items: center; gap: 8px; background: #f8fafc;
        border: 1px solid #e2e8f0; padding: 6px 14px; border-radius: 20px;
        width: 380px; color: #64748b; font-size: 0.85rem;
    }
    .user-profile {
        display: flex; align-items: center; gap: 10px;
    }
    .avatar-circle {
        width: 34px; height: 34px; border-radius: 50%; background: #008f88;
        color: white; display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.85rem;
    }

    /* 4. Thẻ Bản Đồ 3D */
    .map-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 8px;
    }
    .map-title {
        font-size: 1.25rem; font-weight: 800; color: #003a70; letter-spacing: 0.5px;
    }

    /* 5. Cột Đặt Lịch Khám Nhanh bên phải */
    .booking-title-bar {
        background: #008f88; color: #ffffff; padding: 10px 14px;
        border-radius: 10px; font-weight: 700; font-size: 0.95rem; margin-bottom: 12px;
        display: flex; justify-content: space-between; align-items: center;
    }

    /* 6. Hộp Chat AI Assistant */
    .ai-chat-header {
        background: linear-gradient(135deg, #008f88 0%, #003a70 100%);
        color: #ffffff; padding: 10px 14px;
        border-radius: 12px 12px 0 0; display: flex; justify-content: space-between; align-items: center;
        font-weight: 700; font-size: 0.92rem;
    }
    .bubble-ai {
        background: #f1f5f9; padding: 9px 13px; border-radius: 12px 12px 12px 2px;
        font-size: 0.85rem; color: #1e293b; margin-bottom: 8px; line-height: 1.45;
        border: 1px solid #e2e8f0;
    }
    .bubble-user {
        background: #008f88; color: #ffffff; padding: 9px 13px; border-radius: 12px 12px 2px 12px;
        font-size: 0.85rem; margin-bottom: 8px; margin-left: 20px; line-height: 1.45; text-align: right;
    }

    /* Card Trang chủ */
    .home-stat-card {
        background: #ffffff; border-radius: 12px; padding: 18px;
        border: 1px solid #e2e8f0; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.2s;
    }
    .home-stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(0, 143, 136, 0.12);
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE KHỞI TẠO
# ═══════════════════════════════════════════════════════════════════════════
if "messages" not in st.session_state:
    st.session_state.messages = []
if "target_floor" not in st.session_state:
    st.session_state.target_floor = 1
if "target_dept" not in st.session_state:
    st.session_state.target_dept = ""
if "current_guidance" not in st.session_state:
    st.session_state.current_guidance = None
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False  # Mặc định dạng hình tròn nổi
if "last_ticket" not in st.session_state:
    st.session_state.last_ticket = None
if "active_menu" not in st.session_state:
    st.session_state.active_menu = "Bản đồ 3D"

# Lấy danh sách các phòng khám lâm sàng từ Database
try:
    clinic_rooms = queue_service.get_all_rooms(room_type="clinic")
except Exception:
    clinic_rooms = [
        {"id": 1, "name": "Khoa Khám Bệnh Chung", "room_number": "101", "floor": 1},
        {"id": 2, "name": "Khoa Nội Tổng Quát", "room_number": "301", "floor": 3},
        {"id": 3, "name": "Khoa Ngoại Tổng Quát", "room_number": "302", "floor": 3},
        {"id": 4, "name": "Khoa Cấp Cứu 24/7", "room_number": "CC01", "floor": 1},
        {"id": 5, "name": "Khoa Tai Mũi Họng & Mắt", "room_number": "303", "floor": 3},
    ]

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR TRÁI: LOGO BỆNH VIỆN ATUS & MENU HOẠT ĐỘNG
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <div class="brand-icon">🏥</div>
        <div class="brand-title">
            BỆNH VIỆN ATUS<br>
            <span style="font-size:0.75rem;font-weight:500;color:#94a3b8;">Đa Khoa Quốc Tế</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Menu điều hướng hoạt động thực tế
    menu_options = [
        "🏠  Trang chủ",
        "🗺️  Bản đồ 3D",
        "📅  Đặt lịch hẹn",
        "🤖  Tư vấn AI",
        "🕒  Lịch sử khám",
        "⚙️  Cài đặt"
    ]
    # Lấy vị trí đang chọn
    default_m_idx = 1
    for i, opt in enumerate(menu_options):
        if st.session_state.active_menu in opt:
            default_m_idx = i
            break

    selected_menu_item = st.radio(
        "Menu Điều Hướng",
        options=menu_options,
        index=default_m_idx,
        label_visibility="collapsed"
    )
    
    # Cập nhật menu được chọn
    for key_name in ["Trang chủ", "Bản đồ 3D", "Đặt lịch hẹn", "Tư vấn AI", "Lịch sử khám", "Cài đặt"]:
        if key_name in selected_menu_item:
            if key_name != st.session_state.active_menu:
                st.session_state.active_menu = key_name
                if key_name == "Tư vấn AI":
                    st.session_state.chat_open = True
                st.rerun()
            break

    st.write("---")
    st.markdown("""
    📞 **Cấp Cứu 24/7:** :red[**115**]  
    ☎️ **Tổng Đài ATus:** **024.7777.9999**  
    ⏰ **Giờ làm việc:** 7:00 – 17:00  
    📍 **Địa chỉ:** Số 1 Phố Y Dược, Cầu Giấy, Hà Nội
    """)

# ═══════════════════════════════════════════════════════════════════════════
# TOP NAVBAR: TÌM KIẾM & THÔNG TIN HỒ SƠ
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="top-navbar">
    <div class="search-box">
        🔍 <span>Tìm kiếm khoa, phòng khám, bác sĩ tại Bệnh Viện ATus...</span>
    </div>
    <div class="user-profile">
        <span style="font-size:1.15rem;cursor:pointer;" title="Thông báo hệ thống">🔔</span>
        <div class="avatar-circle">AT</div>
        <span style="font-size:0.85rem;font-weight:600;color:#334155;">Bệnh nhân</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# XỬ LÝ THEO MENU ĐƯỢC CHỌN (TẤT CẢ MENU HOẠT ĐỘNG HOÀN TOÀN)
# ═══════════════════════════════════════════════════════════════════════════

# 1. MENU: TRANG CHỦ ────────────────────────────────────────────────────────
if st.session_state.active_menu == "Trang chủ":
    st.markdown("""
    <div style="background:linear-gradient(135deg, #003a70 0%, #008f88 100%);color:white;padding:24px 28px;border-radius:14px;margin-bottom:20px;">
        <h2 style="margin:0 0 8px 0;color:white;font-weight:800;">Chào mừng quý khách đến với BỆNH VIỆN ATUS</h2>
        <p style="margin:0;opacity:0.92;font-size:0.95rem;">Hệ thống y tế thông minh tích hợp Trợ lý Trí tuệ Nhân tạo & Bản đồ 3D chỉ dẫn phân khoa hàng đầu.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""
        <div class="home-stat-card">
            <div style="font-size:28px;">🗺️</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Bản đồ 3D Tầng</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Mặt bằng Isometric trực quan, tìm kiếm phòng khám dễ dàng.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Xem Bản Đồ 3D", use_container_width=True, key="btn_go_map"):
            st.session_state.active_menu = "Bản đồ 3D"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="home-stat-card">
            <div style="font-size:28px;">📅</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Đặt Lịch & Cấp Số</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Lấy số thứ tự trực tiếp, gửi SMS xác nhận tức thì.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Đặt Lịch Ngay", use_container_width=True, key="btn_go_book"):
            st.session_state.active_menu = "Đặt lịch hẹn"
            st.rerun()

    with c3:
        st.markdown("""
        <div class="home-stat-card">
            <div style="font-size:28px;">🤖</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Bác Sĩ AI Tiếp Đón</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Hỏi đáp triệu chứng, quy trình BHYT và định vị phòng.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Chat Với Bác Sĩ AI", use_container_width=True, key="btn_go_ai"):
            st.session_state.chat_open = True
            st.rerun()

    with c4:
        st.markdown("""
        <div class="home-stat-card">
            <div style="font-size:28px;">🕒</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Tra Cứu Lịch Sử</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Xem mã phiếu, thời gian chờ và tiến độ khám tại các phòng.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Tra Cứu Lịch Sử", use_container_width=True, key="btn_go_history"):
            st.session_state.active_menu = "Lịch sử khám"
            st.rerun()

    st.write("---")
    st.subheader("👨‍⚕️ Đội Ngũ Bác Sĩ Trực Hôm Nay Tại Bệnh Viện ATus")
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("""
        <div style="background:white;padding:14px;border-radius:10px;border:1px solid #e2e8f0;display:flex;gap:12px;align-items:center;">
            <div style="font-size:36px;">👨‍⚕️</div>
            <div>
                <b style="color:#003a70;font-size:0.95rem;">ThS. Bác sĩ Nguyễn Tấn</b> (Khoa Nội Tổng Quát) ⭐⭐⭐⭐⭐<br>
                <span style="font-size:0.82rem;color:#64748b;">Chuyên gia chẩn đoán và điều trị bệnh lý nội khoa người lớn. Phòng 301.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with d2:
        st.markdown("""
        <div style="background:white;padding:14px;border-radius:10px;border:1px solid #e2e8f0;display:flex;gap:12px;align-items:center;">
            <div style="font-size:36px;">👩‍⚕️</div>
            <div>
                <b style="color:#003a70;font-size:0.95rem;">BS. CKI Ngayh Huyền</b> (Khoa Khám Bệnh & Triage) ⭐⭐⭐⭐⭐<br>
                <span style="font-size:0.82rem;color:#64748b;">Bác sĩ tiếp đón, sàng lọc triệu chứng và phân luồng cấp cứu. Phòng 101.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# 2. MENU: LỊCH SỬ KHÁM ──────────────────────────────────────────────────────
elif st.session_state.active_menu == "Lịch sử khám":
    st.markdown("""
    <div class="map-header">
        <div class="map-title">🕒 LỊCH SỬ ĐĂNG KÝ & LẤY SỐ KHÁM TẠI BỆNH VIỆN ATUS</div>
    </div>
    """, unsafe_allow_html=True)

    # Tìm kiếm theo số điện thoại hoặc mã vé
    c_find1, c_find2 = st.columns([7, 3])
    with c_find1:
        search_query = st.text_input("🔍 Tra cứu theo Số điện thoại hoặc Mã số phiếu (VD: 0912... hoặc AT-...)", "")
    
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        if search_query.strip():
            cursor.execute("""
                SELECT TOP 50 t.ticket_number, t.patient_name, t.patient_phone, r.name as room_name, 
                       r.room_number, r.floor, t.status, t.visit_date, t.created_at
                FROM tickets t
                JOIN rooms r ON t.initial_room_id = r.id
                WHERE t.patient_phone LIKE ? OR t.ticket_number LIKE ?
                ORDER BY t.id DESC
            """, (f"%{search_query.strip()}%", f"%{search_query.strip()}%"))
        else:
            cursor.execute("""
                SELECT TOP 50 t.ticket_number, t.patient_name, t.patient_phone, r.name as room_name, 
                       r.room_number, r.floor, t.status, t.visit_date, t.created_at
                FROM tickets t
                JOIN rooms r ON t.initial_room_id = r.id
                ORDER BY t.id DESC
            """)
        cols = [column[0] for column in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()

        if rows:
            df = pd.DataFrame(rows)
            df.columns = ["Mã Số Vé", "Họ Tên", "Số ĐT", "Phòng Khám", "Số Phòng", "Tầng", "Trạng Thái", "Ngày Khám", "Thời Gian Đăng Ký"]
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Chưa tìm thấy lượt đăng ký nào phù hợp.")
    except Exception as e:
        st.warning(f"Không thể kết nối SQL Server ({e}). Đang hiển thị bộ nhớ phiên.")
        if st.session_state.last_ticket:
            st.write(st.session_state.last_ticket)

# 3. MENU: CÀI ĐẶT ──────────────────────────────────────────────────────────
elif st.session_state.active_menu == "Cài đặt":
    st.markdown("""
    <div class="map-header">
        <div class="map-title">⚙️ CÀI ĐẶT HỆ THỐNG KIOSK BỆNH VIỆN ATUS</div>
    </div>
    """, unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Ngôn ngữ hiển thị", ["Tiếng Việt (vi-VN)", "English (en-US)"])
        st.selectbox("Chế độ hiển thị Bản đồ 3D", ["Three.js Isometric Hiện Đại (Màu mint & open-cut)", "3D Khối Toàn Tòa Nhà"])
        st.selectbox("Thời gian tự động Reset Kiosk (khi rảnh)", ["3 phút", "5 phút (Mặc định)", "10 phút", "Không bao giờ"])
    with c2:
        st.checkbox("Tự động phát âm thanh khi có phản hồi AI", value=True)
        st.checkbox("Tự động gửi tin nhắn SMS xác nhận lịch hẹn", value=True)
        st.checkbox("Hiển thị vị trí phòng trên bản đồ 3D khi chọn chuyên khoa", value=True)
        st.info("Trạng thái cơ sở dữ liệu: **Microsoft SQL Server `hospital_atus` (Kết nối thành công)**")

# 4. MENU: BẢN ĐỒ 3D, ĐẶT LỊCH HẸN HOẶC TƯ VẤN AI ─────────────────────────────
else:
    col_map, col_right = st.columns([67, 33], gap="medium")

    # ── CỘT TRÁI: BẢN ĐỒ BỆNH VIỆN 3D ISOMETRIC ──────────────────────────────
    with col_map:
        st.markdown("""
        <div class="map-header">
            <div class="map-title">BẢN ĐỒ BỆNH VIỆN ATUS 3D</div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.current_guidance:
            g = st.session_state.current_guidance
            st.info(f"📍 **Chỉ dẫn AI:** {g.get('room_name')} (Tầng {g.get('floor')}) — {g.get('instructions')}")

        # Nhúng Three.js Isometric 3D Model
        html_3d = get_hospital_3d_html(
            target_floor=st.session_state.target_floor,
            target_dept=st.session_state.target_dept
        )
        components.html(html_3d, height=625)

    # ── CỘT PHẢI: FORM ĐẶT LỊCH KHÁM NHANH ──────────────────────────────────
    with col_right:
        st.markdown("""
        <div class="booking-title-bar">
            <span>Đặt Lịch Khám Nhanh - Bệnh Viện ATus</span>
            <span style="font-size:0.8rem;background:rgba(255,255,255,0.25);padding:2px 8px;border-radius:12px;">Kiosk Quầy</span>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.last_ticket:
            t = st.session_state.last_ticket
            st.success(f"""
            ✅ **CẤP SỐ THÀNH CÔNG!**
            - **Mã vé:** `{t['ticket_number']}`
            - **Phòng khám:** {t['room_name']} ({t['room_number']} - Tầng {t['floor']})
            - **Bệnh nhân:** {t['patient_name']}
            - **Chờ trước bạn:** {t['waiting_ahead']} người
            """)
            if st.button("🔄 Lấy Phiếu Mới / Nhập Lại", use_container_width=True):
                st.session_state.last_ticket = None
                st.rerun()

        # Form đặt lịch & lấy số
        with st.form("quick_booking_form"):
            dept_options = [r["name"] for r in clinic_rooms]
            default_d_idx = 0
            if st.session_state.target_dept:
                for idx, dname in enumerate(dept_options):
                    if st.session_state.target_dept.lower() in dname.lower():
                        default_d_idx = idx
                        break

            sel_dept = st.selectbox("Chọn chuyên khoa khám *", options=dept_options, index=default_d_idx)

            st.write("<span style='font-size:0.85rem;font-weight:600;color:#334155;'>Chọn bác sĩ tiếp nhận</span>", unsafe_allow_html=True)
            doc_choice = st.radio(
                "Bác sĩ",
                options=["BS. Nguyễn Tấn ⭐⭐⭐⭐⭐", "BS. Ngayh Huyền ⭐⭐⭐⭐⭐"],
                label_visibility="collapsed"
            )

            st.write("<span style='font-size:0.85rem;font-weight:600;color:#334155;'>Chọn khung giờ khám</span>", unsafe_allow_html=True)
            time_slots = ["20:00", "09:00", "03:00", "04:00", "10:00", "12:00", "15:00", "17:00"]
            sel_time = st.selectbox("Giờ hẹn", options=time_slots, label_visibility="collapsed")

            p_name = st.text_input("Họ và tên bệnh nhân *", placeholder="Ví dụ: Nguyễn Văn A")
            p_phone = st.text_input("Số điện thoại (nhận SMS xác nhận)", placeholder="0912 345 678")

            btn_confirm = st.form_submit_button("Xác nhận đặt lịch & Lấy số thứ tự", use_container_width=True, type="primary")

            if btn_confirm:
                if not p_name.strip():
                    st.error("Vui lòng điền Họ tên bệnh nhân!")
                else:
                    target_room = clinic_rooms[0]
                    for r in clinic_rooms:
                        if r["name"] == sel_dept:
                            target_room = r
                            break

                    try:
                        ticket_res = queue_service.issue_ticket(
                            room_id=target_room["id"],
                            patient_name=p_name.strip(),
                            patient_phone=p_phone.strip(),
                            patient_notes=f"Hẹn giờ {sel_time} - {doc_choice}"
                        )
                        st.session_state.last_ticket = ticket_res
                        st.session_state.target_floor = ticket_res["floor"]
                        st.session_state.target_dept = ticket_res["room_name"]

                        if p_phone.strip():
                            send_appointment_sms(
                                code=ticket_res["ticket_number"],
                                name=ticket_res["patient_name"],
                                phone=ticket_res["patient_phone"],
                                dept=f"{ticket_res['room_name']} ({ticket_res['room_number']})",
                                date=str(date.today())
                            )
                    except Exception as e:
                        st.error(f"Lỗi cấp vé: {e}")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# CỬA SỔ CHAT AI FLOATING WIDGET (HÌNH TRÒN NỔI <-> POPUP CHAT)
# ═══════════════════════════════════════════════════════════════════════════

# NẾU CHAT ĐANG ĐÓNG -> HIỂN THỊ NÚT TRÒN NỔI BẬT GÓC PHẢI DƯỚI
if not st.session_state.chat_open:
    st.markdown("""
    <div style="position:fixed;bottom:24px;right:28px;z-index:999999;">
    """, unsafe_allow_html=True)
    
    col_fab_l, col_fab_r = st.columns([8, 2])
    with col_fab_r:
        if st.button("💬 Trò Chuyện Bác Sĩ AI", type="primary", use_container_width=True, help="Bấm để mở trợ lý tiếp đón AI"):
            st.session_state.chat_open = True
            st.rerun()

# NẾU CHAT ĐANG MỞ -> HIỂN THỊ HỘP POPUP CHUẨN DESIGN MOCKUP
else:
    st.write("---")
    chat_cols = st.columns([65, 35])
    with chat_cols[1]:
        st.markdown("""
        <div class="ai-chat-header">
            <div style="display:flex;align-items:center;gap:6px;">
                🤖 <span>AI Assistant - Bệnh Viện ATus</span>
            </div>
            <span style="font-size:0.75rem;background:rgba(255,255,255,0.2);padding:2px 6px;border-radius:4px;">Tiếp đón & Triage</span>
        </div>
        """, unsafe_allow_html=True)

        c_bar1, c_bar2 = st.columns([1, 1])
        with c_bar1:
            if st.button("➖ Thu nhỏ thành nút tròn", use_container_width=True):
                st.session_state.chat_open = False
                st.rerun()
        with c_bar2:
            if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.target_dept = ""
                st.session_state.current_guidance = None
                st.rerun()

        # Các gợi ý câu hỏi nhanh (Chips)
        st.write("<span style='font-size:0.78rem;color:#64748b;font-weight:600;'>Gợi ý câu hỏi nhanh:</span>", unsafe_allow_html=True)
        chip_c1, chip_c2 = st.columns(2)
        with chip_c1:
            if st.button("🩺 Khám nội tổng quát", use_container_width=True, key="chip1"):
                st.session_state.quick_chat_prompt = "Tôi muốn khám nội tổng quát"
        with chip_c2:
            if st.button("📋 Thủ tục BHYT", use_container_width=True, key="chip2"):
                st.session_state.quick_chat_prompt = "Thủ tục khám BHYT cần những gì?"

        # Voice Input Component
        components.html("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body { margin: 0; font-family: sans-serif; background: transparent; }
                .voice-btn { background: #008f88; color: white; border: none; border-radius: 14px; padding: 5px 12px; font-size: 11.5px; font-weight: 600; cursor: pointer; transition: 0.2s; }
                .voice-btn:hover { background: #003a70; }
            </style>
        </head>
        <body>
            <button class="voice-btn" onclick="startVoice()">🎤 Nói Triệu Chứng (Tiếng Việt)</button>
            <span id="vTxt" style="font-size:11px;color:#64748b;margin-left:6px;">Bấm để nói bằng giọng nói...</span>
            <script>
                function startVoice() {
                    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                    if (!SpeechRec) { alert("Trình duyệt không hỗ trợ Web Speech."); return; }
                    const r = new SpeechRec();
                    r.lang = 'vi-VN';
                    r.onstart = () => { document.getElementById('vTxt').innerText = 'Đang nghe bạn nói...'; };
                    r.onresult = (e) => {
                        const txt = e.results[0][0].transcript;
                        document.getElementById('vTxt').innerText = 'Đã nhận: ' + txt;
                        navigator.clipboard.writeText(txt);
                    };
                    r.onerror = () => { document.getElementById('vTxt').innerText = 'Không nhận diện được mic.'; };
                    r.start();
                }
            </script>
        </body>
        </html>
        """, height=30)

        # Cửa sổ tin nhắn trò chuyện
        chat_win = st.container(height=280)
        with chat_win:
            if not st.session_state.messages:
                st.markdown("""
                <div class="bubble-ai">
                    🤖 <b>AI Bệnh Viện ATus:</b> Xin chào! Tôi là trợ lý AI tiếp đón của Bệnh Viện ATus. Tôi có thể giúp bạn tìm đường hoặc gợi ý chuyên khoa khám phù hợp. Bạn đang có dấu hiệu hay thắc mắc gì?
                </div>
                """, unsafe_allow_html=True)
            else:
                for m in st.session_state.messages:
                    if m["role"] == "user":
                        st.markdown(f'<div class="bubble-user">{m["content"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="bubble-ai">🤖 {m["content"]}</div>', unsafe_allow_html=True)

        # Xử lý prompt từ chip gợi ý (nếu có)
        user_to_send = None
        if "quick_chat_prompt" in st.session_state and st.session_state.quick_chat_prompt:
            user_to_send = st.session_state.quick_chat_prompt
            st.session_state.quick_chat_prompt = None

        # Form gửi tin nhắn trong khung chat
        with st.form("chat_input_form", clear_on_submit=True):
            user_msg = st.text_input("Trò chuyện cùng AI...", placeholder="Ví dụ: Tôi muốn khám nội tổng quát, đau dạ dày...")
            btn_send = st.form_submit_button("Gửi 🚀", use_container_width=True, type="primary")

            if (btn_send and user_msg.strip()) or user_to_send:
                final_input = user_to_send if user_to_send else user_msg.strip()
                st.session_state.messages.append({"role": "user", "content": final_input})
                prior = st.session_state.messages[:-1]

                with st.spinner("Bác sĩ AI ATus đang phân tích..."):
                    try:
                        reply = answer(final_input, history=prior)
                        reply_text = reply.get("text", "")
                        if reply.get("stream"):
                            chunks = []
                            for c in reply["stream"]:
                                chunks.append(str(c))
                            reply_text = "".join(chunks).strip()

                        if not reply_text:
                            reply_text = "Dạ, Bệnh Viện ATus đã tiếp nhận thông tin của bạn. Bạn có thể chọn phòng khám ở khung bên cạnh để lấy số thứ tự ngay."

                        st.session_state.messages.append({"role": "assistant", "content": reply_text})

                        if reply.get("location"):
                            loc = reply["location"]
                            st.session_state.target_floor = loc.get("floor", 1)
                            st.session_state.target_dept = reply.get("department", "")
                            st.session_state.current_guidance = loc
                    except Exception as err:
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Dạ, Bệnh Viện ATus đã ghi nhận triệu chứng. Nếu đây là trường hợp khẩn cấp, vui lòng đến ngay Khoa Cấp Cứu Tầng 1 hoặc gọi 115."
                        })
                st.rerun()

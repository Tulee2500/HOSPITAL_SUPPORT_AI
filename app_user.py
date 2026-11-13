"""Giao diện Cổng Bệnh Nhân & Kiosk Tiếp Đón (AI Hospital Assistant & Map - Bệnh Viện ATus).
Thiết kế chính xác theo toàn bộ bộ mockup thiết kế UI/UX:
1. "Bản đồ 3D": Mặt bằng Isometric Three.js, Đặt Lịch Khám Nhanh bên phải, AI Assistant góc phải dưới.
2. "Đặt lịch hẹn": Bước 1 Chọn Chuyên khoa & Dịch vụ, Bước 2 Chọn Bác sĩ, Bước 3 Chọn Ngày & Giờ (Lưới slot Còn chỗ/Đầy), Mini Map & AI Assistant.
3. "Tư vấn AI": Cột chat trực tuyến 24/7 với gợi ý câu hỏi, voice mic, nút điều hướng đặt lịch/xem bản đồ trong câu trả lời, Mini Map & Popup Đặt lịch nhanh AI.
4. "Lịch sử khám": Lọc theo thời gian & trạng thái, timeline thẻ lịch sử khám, thẻ "Lượt khám sắp tới", Mini Map & AI Assistant.
5. "Trang chủ": Dashboard tổng quan khoa khám, bác sĩ trực, các lối tắt tiện ích.
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime
import pandas as pd
import json

import queue_service
import db
import patient_service
import ticket_service
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
# TÙY BIẾN CSS TOÀN DIỆN CHUẨN MOCKUP DESIGN
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* 1. NÚT MỞ SIDEBAR LUÔN HIỂN THỊ KHI SIDEBAR BỊ ẨN */
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 9999999 !important;
        position: fixed !important;
        top: 12px !important;
        left: 12px !important;
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
        box-shadow: 0 4px 12px rgba(0, 58, 112, 0.35) !important;
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
        padding-top: 0.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
        max-width: 100% !important;
        background-color: #f6f9fa;
    }
    
    /* 2. Thanh Sidebar bên trái (#003a70 Navy) */
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
        width: 40px; height: 40px; background: #ffffff;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-size: 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }
    .brand-title {
        font-size: 1.05rem; font-weight: 800; line-height: 1.2; letter-spacing: 0.5px;
    }

    /* Menu Sidebar */
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

    /* 3. Top Navbar Bar */
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

    /* Tiêu đề & Nút đặt lịch ở góc trên */
    .page-title-row {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 12px;
    }
    .page-title-text {
        font-size: 1.25rem; font-weight: 800; color: #003a70; letter-spacing: 0.4px; margin: 0;
    }
    .page-subtitle-text {
        font-size: 0.85rem; color: #64748b; margin-top: 2px;
    }

    /* Thẻ Chung (Cards) */
    .white-card {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); margin-bottom: 12px;
    }

    /* Khối Chọn Chuyên Khoa Dạng Card (Bước 1 Đặt Lịch) */
    .dept-card {
        background: #ffffff; border: 1.5px solid #e2e8f0; border-radius: 10px;
        padding: 12px 10px; text-align: center; cursor: pointer; transition: all 0.2s ease;
    }
    .dept-card:hover {
        border-color: #008f88; background: #f0fdfa; transform: translateY(-2px);
    }
    .dept-card.active {
        border-color: #008f88; background: #e6f7f6; box-shadow: 0 2px 8px rgba(0,143,136,0.15);
    }
    .dept-card-icon {
        font-size: 26px; margin-bottom: 6px;
    }
    .dept-card-title {
        font-size: 0.84rem; font-weight: 700; color: #0f172a; line-height: 1.2;
    }

    /* Khối Chọn Bác Sĩ (Bước 2 Đặt Lịch) */
    .doctor-card {
        background: #ffffff; border: 1.5px solid #e2e8f0; border-radius: 10px;
        padding: 12px; display: flex; gap: 12px; align-items: center;
        transition: all 0.2s ease; margin-bottom: 8px;
    }
    .doctor-card.active {
        border-color: #008f88; background: #f0fdfa;
    }
    .doc-avatar {
        width: 44px; height: 44px; border-radius: 50%; background: #e0f2fe;
        display: flex; align-items: center; justify-content: center; font-size: 24px;
    }

    /* KHỐI ĐẶT LỊCH KHÁM NHANH CHUẨN MOCKUP (THIẾT KẾ CARD HIỆN ĐẠI) */
    .quick-booking-box {
        background: #ffffff;
        border: 1.5px solid #e2e8f0;
        border-radius: 14px;
        padding: 20px 22px;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.04);
        margin-bottom: 16px;
    }
    .quick-booking-title {
        font-size: 1.18rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 14px;
        letter-spacing: -0.3px;
    }
    .quick-section-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 6px;
        display: block;
    }

    /* Lưới Slot Lịch Khám (Bước 3) */
    .slot-badge-green {
        background: #ccfbf1; color: #0f766e; font-weight: 700; font-size: 0.75rem;
        padding: 4px 8px; border-radius: 6px; text-align: center; display: inline-block;
        border: 1px solid #99f6e4;
    }
    .slot-badge-gray {
        background: #f1f5f9; color: #94a3b8; font-weight: 600; font-size: 0.75rem;
        padding: 4px 8px; border-radius: 6px; text-align: center; display: inline-block;
        border: 1px solid #e2e8f0;
    }

    /* Khung Chat AI Assistant (Mockup Stream) */
    .chat-bubble-row {
        display: flex; gap: 10px; margin-bottom: 12px; align-items: flex-start;
    }
    .chat-bubble-avatar {
        width: 34px; height: 34px; border-radius: 50%; display: flex;
        align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0;
    }
    .chat-bubble-content {
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px;
        padding: 10px 14px; font-size: 0.88rem; line-height: 1.45; color: #1e293b;
        max-width: 82%;
    }
    .chat-bubble-user-content {
        background: #008f88; color: #ffffff; border-radius: 14px;
        padding: 10px 14px; font-size: 0.88rem; line-height: 1.45; margin-left: auto;
        max-width: 82%;
    }

    /* Floating Action Button (FAB) AI Assistant nổi góc phải dưới */
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 22px !important;
        right: 26px !important;
        z-index: 9999999 !important;
    }
    div[data-testid="stPopover"] > button {
        background: linear-gradient(135deg, #008f88 0%, #003a70 100%) !important;
        color: #ffffff !important;
        border-radius: 999px !important;
        padding: 10px 20px !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
        box-shadow: 0 6px 22px rgba(0, 58, 112, 0.42) !important;
        border: 2px solid #ffffff !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        transition: all 0.25s ease !important;
        cursor: pointer !important;
    }
    div[data-testid="stPopover"] > button:hover {
        transform: translateY(-2px) scale(1.04) !important;
        box-shadow: 0 8px 28px rgba(0, 143, 136, 0.55) !important;
    }
    div[data-testid="stPopoverBody"] {
        width: 400px !important;
        max-width: 92vw !important;
        max-height: 560px !important;
        border-radius: 16px !important;
        box-shadow: 0 16px 42px rgba(0,0,0,0.28) !important;
        border: 2px solid #008f88 !important;
        padding: 16px !important;
        background: #ffffff !important;
    }

    /* Card Mini Map góc trên bên phải */
    .minimap-card {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 10px; margin-bottom: 12px; position: relative;
    }
    .minimap-top-btn {
        position: absolute; top: 14px; right: 14px; z-index: 10;
        background: #008f88; color: #ffffff; font-size: 0.75rem; font-weight: 700;
        padding: 3px 10px; border-radius: 6px; border: none; cursor: pointer;
    }

    /* Lịch sử khám: Thẻ Timeline */
    .history-card {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 14px; margin-bottom: 12px; position: relative;
        transition: box-shadow 0.2s;
    }
    .history-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    .badge-status-done {
        background: #ecfdf5; color: #047857; font-size: 0.76rem; font-weight: 700;
        padding: 2px 8px; border-radius: 6px; border: 1px solid #a7f3d0;
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
    st.session_state.chat_open = False
if "last_ticket" not in st.session_state:
    st.session_state.last_ticket = None
if "lang" not in st.session_state:
    st.session_state.lang = "vi"
if "patient_mpi_found" not in st.session_state:
    st.session_state.patient_mpi_found = None
if "patient_name_val" not in st.session_state:
    st.session_state.patient_name_val = "Nguyễn Văn A"
if "patient_phone_val" not in st.session_state:
    st.session_state.patient_phone_val = "0912 345 678"
if "patient_cccd_val" not in st.session_state:
    st.session_state.patient_cccd_val = ""
if "active_menu" not in st.session_state:
    st.session_state.active_menu = "Bản đồ 3D"
if "selected_booking_dept" not in st.session_state:
    st.session_state.selected_booking_dept = "Khoa Nội tổng quát"
if "selected_booking_doc" not in st.session_state:
    st.session_state.selected_booking_doc = "PGS.TS. Nguyễn Văn A"
if "selected_booking_slot" not in st.session_state:
    st.session_state.selected_booking_slot = "08:00"

# Lấy danh sách phòng khám từ Database
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

    menu_options = [
        "🏠  Trang chủ",
        "🗺️  Bản đồ 3D",
        "📅  Đặt lịch hẹn",
        "🤖  Tư vấn AI",
        "🕒  Lịch sử khám",
        "⚙️  Cài đặt"
    ]
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
    
    for key_name in ["Trang chủ", "Bản đồ 3D", "Đặt lịch hẹn", "Tư vấn AI", "Lịch sử khám", "Cài đặt"]:
        if key_name in selected_menu_item:
            if key_name != st.session_state.active_menu:
                st.session_state.active_menu = key_name
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
# TOP NAVBAR: TÌM KIẾM, ĐỔI NGÔN NGỮ & RESET KIOSK (PHASE 2)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="top-navbar">
    <div style="display:flex;align-items:center;gap:10px;">
        <span style="font-weight:800;color:#003a70;font-size:1.05rem;">🏥 KIOSK TIẾP ĐÓN THÔNG MINH</span>
        <span style="background:#ecfdf5;color:#059669;font-size:0.75rem;font-weight:700;padding:2px 8px;border-radius:12px;border:1px solid #a7f3d0;">● Trực tuyến 24/7</span>
    </div>
    <div class="user-profile">
        <span style="font-size:1.15rem;cursor:pointer;" title="Thông báo hệ thống">🔔</span>
        <div class="avatar-circle">AT</div>
        <span style="font-size:0.85rem;font-weight:600;color:#334155;">
            """ + (f"Bệnh nhân: {st.session_state.patient_mpi_found}" if st.session_state.patient_mpi_found else "Kiosk Khách (Chưa định danh)") + """
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

col_nb1, col_nb2, col_nb3 = st.columns([55, 25, 20])
with col_nb1:
    search_q = st.text_input("🔍 Tìm kiếm", placeholder="🔍 Tìm kiếm chuyên khoa, phòng khám, bác sĩ...", label_visibility="collapsed")
    if search_q.strip() and search_q.strip() != st.session_state.target_dept:
        st.session_state.target_dept = search_q.strip()
with col_nb2:
    lang_opts = ["🇻🇳 Tiếng Việt (vi-VN)", "🇬🇧 English (en-US)"]
    cur_lang_idx = 0 if st.session_state.lang == "vi" else 1
    sel_lang = st.selectbox("Ngôn ngữ Kiosk", options=lang_opts, index=cur_lang_idx, label_visibility="collapsed")
    new_lang = "vi" if "Tiếng Việt" in sel_lang else "en"
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
with col_nb3:
    if st.button("🔄 Reset Kiosk", use_container_width=True, help="Xóa thông tin phiên làm việc hiện tại để bảo vệ quyền riêng tư người bệnh"):
        st.session_state.last_ticket = None
        st.session_state.patient_mpi_found = None
        st.session_state.patient_name_val = ""
        st.session_state.patient_phone_val = ""
        st.session_state.patient_cccd_val = ""
        st.session_state.target_dept = ""
        st.session_state.messages = []
        st.rerun()

# Client-side Inactivity Timeout (Tự động tải lại màn hình sau 45s không thao tác)
components.html("""
<script>
let lastActive = Date.now();
const TIMEOUT_MS = 45000; // 45 giây không thao tác

function recordActivity() {
    lastActive = Date.now();
}
window.addEventListener('mousemove', recordActivity, true);
window.addEventListener('keydown', recordActivity, true);
window.addEventListener('touchstart', recordActivity, true);
window.addEventListener('click', recordActivity, true);

setInterval(() => {
    if (Date.now() - lastActive > TIMEOUT_MS) {
        lastActive = Date.now();
        window.parent.location.reload();
    }
}, 4000);
</script>
""", height=0)


# ═══════════════════════════════════════════════════════════════════════════
# TRANG 1: BẢN ĐỒ 3D (CHÍNH XÁC MOCKUP 1)
# ═══════════════════════════════════════════════════════════════════════════
if st.session_state.active_menu == "Bản đồ 3D":
    st.markdown("""
    <div class="page-title-row">
        <div>
            <h2 class="page-title-text">BẢN ĐỒ BỆNH VIỆN 3D</h2>
            <div class="page-subtitle-text">Mặt bằng trực quan Three.js Isometric - Tầng 1, 2, 3</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_map, c_side = st.columns([73, 27], gap="medium")

    with c_map:
        if st.session_state.current_guidance:
            g = st.session_state.current_guidance
            st.info(f"📍 **Chỉ dẫn AI:** {g.get('room_name')} (Tầng {g.get('floor')}) — {g.get('instructions')}")

        html_3d = get_hospital_3d_html(
            target_floor=st.session_state.target_floor,
            target_dept=st.session_state.target_dept,
            mode="full"
        )
        components.html(html_3d, height=680)

    with c_side:
        # THÔNG TIN KHOA PHÒNG & CHỈ DẪN LỐI ĐI (LOẠI BỎ FORM TRÙNG LẶP)
        st.markdown("""
        <div style="background:#003a70;color:#ffffff;padding:10px 14px;border-radius:10px 10px 0 0;font-weight:700;font-size:0.95rem;display:flex;align-items:center;gap:8px;">
            <span>📍</span> <span>Thông Tin Khoa / Phòng Khám</span>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown("""<div class="white-card" style="border-top:none;border-radius:0 0 10px 10px;margin-bottom:12px;">""", unsafe_allow_html=True)
            
            # Chọn khoa để định vị trên bản đồ 3D
            dept_opts = [r["name"] for r in clinic_rooms]
            cur_idx = 0
            if st.session_state.target_dept:
                for i, d in enumerate(dept_opts):
                    if st.session_state.target_dept.lower() in d.lower() or d.lower() in st.session_state.target_dept.lower():
                        cur_idx = i
                        break

            sel_dept_nav = st.selectbox("Chọn khoa để xem vị trí:", options=dept_opts, index=cur_idx, key="sel_dept_nav_map")

            selected_room_info = clinic_rooms[cur_idx]
            for r in clinic_rooms:
                if r["name"] == sel_dept_nav:
                    selected_room_info = r
                    break

            if selected_room_info["name"] != st.session_state.target_dept:
                st.session_state.target_dept = selected_room_info["name"]
                st.session_state.target_floor = selected_room_info.get("floor", 1)
                st.rerun()

            r_code = selected_room_info.get("room_number", "P.101")
            r_floor = selected_room_info.get("floor", 1)
            is_er = "cấp cứu" in selected_room_info["name"].lower()
            
            st.markdown(f"""
            <div style="padding:12px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin:10px 0;">
                <div style="font-weight:800;color:#003a70;font-size:1.05rem;margin-bottom:4px;">{selected_room_info['name']}</div>
                <div style="font-size:0.85rem;color:#64748b;margin-bottom:8px;">
                    Mã phòng: <b style="color:#0f172a;">{r_code}</b> · Vị trí: <b style="color:#008f88;">Tầng {r_floor}</b>
                </div>
                <div style="font-size:0.82rem;color:#334155;margin-bottom:4px;">⏰ Thời gian tiếp nhận: <b>{"24/7 (Khẩn cấp)" if is_er else "07:00 – 17:00"}</b></div>
                <div style="font-size:0.82rem;color:#334155;">👨‍⚕️ Bác sĩ trực: <b>{"BS. Ngayh Huyền (Cấp Cứu)" if is_er else "ThS. BS. Nguyễn Tấn"}</b></div>
            </div>
            <div style="background:#f0fdfa;border:1px dashed #008f88;border-radius:8px;padding:9px 12px;font-size:0.82rem;color:#0f766e;margin-bottom:12px;">
                🧭 <b>Chỉ dẫn di chuyển:</b> {"Lối đi riêng xe cứu thương bên cánh trái sảnh chính." if is_er else f"Đi thang máy trung tâm lên Tầng {r_floor}, theo dải màu dẫn đường đến phòng {r_code}."}
            </div>
            """, unsafe_allow_html=True)

            if not is_er:
                if st.button("📅 Đặt Lịch Hẹn Tại Khoa Này", use_container_width=True, type="primary", key="btn_switch_to_booking_from_map"):
                    st.session_state.active_menu = "Đặt lịch hẹn"
                    st.session_state.selected_booking_dept = selected_room_info["name"]
                    st.rerun()
            else:
                st.error("🚨 Khoa Cấp Cứu tiếp nhận trực tiếp 24/7 không cần đặt hẹn. Vui lòng di chuyển ngay đến cửa cấp cứu.")

            st.markdown("</div>", unsafe_allow_html=True)

            # Lối tắt chuyển tầng & khu vực nhanh
            st.markdown("""
            <div class="white-card">
                <b style="font-size:0.86rem;color:#003a70;display:block;margin-bottom:8px;">Lối tắt khu vực trọng yếu:</b>
            """, unsafe_allow_html=True)
            k1, k2 = st.columns(2)
            with k1:
                if st.button("🚨 Cấp Cứu 24/7", use_container_width=True, key="btn_quick_er"):
                    st.session_state.target_floor = 1
                    st.session_state.target_dept = "Khoa Cấp Cứu 24/7"
                    st.rerun()
            with k2:
                if st.button("💊 Nhà Thuốc", use_container_width=True, key="btn_quick_pharm"):
                    st.session_state.target_floor = 1
                    st.session_state.target_dept = "Nhà thuốc bệnh viện"
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# TRANG 2: ĐẶT LỊCH HẸN KHÁM BỆNH (CHÍNH XÁC MOCKUP THIẾT KẾ)
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_menu == "Đặt lịch hẹn":
    st.markdown("""
    <div class="page-title-row">
        <div>
            <h2 class="page-title-text">ĐẶT LỊCH HẸN KHÁM BỆNH</h2>
            <div class="page-subtitle-text">Hệ thống chọn khoa, bác sĩ và khung giờ khám tự động chuẩn Kiosk ATus</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_book, c_side = st.columns([46, 54], gap="large")

    with c_book:
        # THẺ "ĐẶT LỊCH KHÁM NHANH" (CHUẨN 100% THEO MOCKUP BÊN TRÁI)
        st.markdown("""
        <div class="quick-booking-box">
            <div class="quick-booking-title">Đặt lịch khám nhanh</div>
            <span class="quick-section-label">Chọn chuyên khoa</span>
        </div>
        """, unsafe_allow_html=True)

        # 1. CHỌN CHUYÊN KHOA (CHỈ CÁC CHUYÊN KHOA NGOẠI TRÚ - KHÔNG CÓ CẤP CỨU)
        outpatient_depts = [
            "Khoa Nội",
            "Khoa Tim mạch",
            "Khoa Nhi",
            "Khoa Sản phụ khoa",
            "Khoa Tai Mũi Họng",
            "Khoa Răng Hàm Mặt",
            "Khoa Mắt",
            "Khoa Da liễu",
            "Khoa Tiêu hóa - Gan mật",
            "Khoa Hô hấp",
            "Khoa Thần kinh",
            "Khoa Cơ Xương Khớp"
        ]
        
        cur_d_idx = 0
        for i, d in enumerate(outpatient_depts):
            if d.lower() in st.session_state.selected_booking_dept.lower() or st.session_state.selected_booking_dept.lower() in d.lower():
                cur_d_idx = i
                break

        sel_dept = st.selectbox(
            "Chọn chuyên khoa",
            options=outpatient_depts,
            index=cur_d_idx,
            label_visibility="collapsed",
            key="sel_quick_dept_box"
        )
        if sel_dept != st.session_state.selected_booking_dept:
            st.session_state.selected_booking_dept = sel_dept
            st.session_state.target_dept = sel_dept
            st.rerun()

        # 2. CHỌN BÁC SĨ (DẠNG THẺ CARD KÈM SỐ SAO ĐÁNH GIÁ)
        st.markdown("<span class='quick-section-label' style='margin-top:12px;'>Chọn bác sĩ</span>", unsafe_allow_html=True)
        
        # Danh sách bác sĩ theo chuyên khoa (chuẩn mockup)
        if "tim" in sel_dept.lower():
            dept_docs = [
                {"name": "BS. Nguyễn Tấn", "stars": "★★★★★", "rating": 5},
                {"name": "BS. Ngô Huyền", "stars": "★★★★☆", "rating": 4}
            ]
        elif "nhi" in sel_dept.lower():
            dept_docs = [
                {"name": "BSCKI. Lê Thị Hương", "stars": "★★★★★", "rating": 5},
                {"name": "BS. Ngô Minh Đức", "stars": "★★★★☆", "rating": 4}
            ]
        elif "mắt" in sel_dept.lower():
            dept_docs = [
                {"name": "BSCKI. Bùi Minh Châu", "stars": "★★★★★", "rating": 5},
                {"name": "BS. Trần Thị Mắt", "stars": "★★★★☆", "rating": 4}
            ]
        else:
            dept_docs = [
                {"name": "BS. Nguyễn Tấn", "stars": "★★★★★", "rating": 5},
                {"name": "BS. Ngô Huyền", "stars": "★★★★☆", "rating": 4}
            ]

        doc_names = [d["name"] for d in dept_docs]
        if st.session_state.selected_booking_doc not in doc_names:
            st.session_state.selected_booking_doc = doc_names[0]

        for d in dept_docs:
            is_doc_active = (st.session_state.selected_booking_doc == d["name"])
            border_color = "#008f88" if is_doc_active else "#e2e8f0"
            bg_color = "#f0fdfa" if is_doc_active else "#ffffff"
            st.markdown(f"""
            <div style="background:{bg_color};border:2px solid {border_color};border-radius:10px;padding:9px 14px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;transition:all 0.2s ease;">
                <span style="font-weight:700;font-size:0.88rem;color:#0f172a;">{d['name']}</span>
                <span style="color:#f59e0b;font-size:0.88rem;letter-spacing:2px;">{d['stars']}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"{'✔ Đang chọn' if is_doc_active else 'Chọn'} {d['name']}", key=f"btn_pick_doc_{d['name']}", use_container_width=True, type="primary" if is_doc_active else "secondary"):
                st.session_state.selected_booking_doc = d["name"]
                st.rerun()

        # 3. CHỌN GIỜ (LƯỚI 9 NÚT BẤM 3x3 CHUẨN MOCKUP)
        st.markdown("<span class='quick-section-label' style='margin-top:12px;'>Chọn giờ</span>", unsafe_allow_html=True)
        time_slot_list = ["08:00", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "16:30", "17:00"]
        
        c_slot1, c_slot2, c_slot3 = st.columns(3)
        cols_slot = [c_slot1, c_slot2, c_slot3]
        for idx, slt in enumerate(time_slot_list):
            with cols_slot[idx % 3]:
                is_slt_active = (st.session_state.selected_booking_slot == slt)
                if st.button(slt, key=f"quick_slt_{slt}", use_container_width=True, type="primary" if is_slt_active else "secondary"):
                    st.session_state.selected_booking_slot = slt
                    st.rerun()

        # 4. THÔNG TIN BỆNH NHÂN (HỌ VÀ TÊN & SỐ ĐIỆN THOẠI)
        st.markdown("<span class='quick-section-label' style='margin-top:14px;'>Thông tin bệnh nhân</span>", unsafe_allow_html=True)
        q_patient_name = st.text_input("Họ và tên", value=st.session_state.patient_name_val, placeholder="Họ và tên", label_visibility="collapsed")
        q_patient_phone = st.text_input("Số điện thoại", value=st.session_state.patient_phone_val, placeholder="Số điện thoại", label_visibility="collapsed")

        # 5. NÚT XÁC NHẬN ĐẶT LỊCH (XANH TEAL #008f88)
        st.write("")
        btn_confirm_quick = st.button("Xác nhận đặt lịch", use_container_width=True, type="primary", key="btn_confirm_quick_appointment")

        if btn_confirm_quick:
            if not q_patient_name.strip() or not q_patient_phone.strip():
                st.error("Vui lòng nhập đầy đủ Họ và tên và Số điện thoại liên hệ!")
            else:
                # Tìm phòng khám tương ứng trong database
                target_room = clinic_rooms[0]
                for r in clinic_rooms:
                    if sel_dept.lower() in r["name"].lower() or r["name"].lower() in sel_dept.lower():
                        target_room = r
                        break
                
                try:
                    tk = queue_service.issue_ticket(
                        room_id=target_room["id"],
                        patient_name=q_patient_name.strip(),
                        patient_phone=q_patient_phone.strip(),
                        cccd=st.session_state.patient_cccd_val or None,
                        patient_notes=f"Khoa: {sel_dept} | Bác sĩ: {st.session_state.selected_booking_doc} | Giờ hẹn: {st.session_state.selected_booking_slot}",
                        priority_level=0,
                        force_emergency=False
                    )
                    st.session_state.last_ticket = tk
                    st.session_state.patient_name_val = q_patient_name.strip()
                    st.session_state.patient_phone_val = q_patient_phone.strip()
                    st.rerun()
                except Exception as ex:
                    st.error(f"Lỗi đặt lịch: {ex}")

    with c_side:
        # BÊN PHẢI: PHIẾU KHÁM ĐIỆN TỬ (NẾU ĐÃ CẤP) HOẶC SƠ ĐỒ 3D PHÒNG KHÁM & TRA CỨU HỒ SƠ
        if st.session_state.last_ticket:
            t_id = st.session_state.last_ticket["ticket_id"]
            t_info = ticket_service.get_ticket_info(t_id) or st.session_state.last_ticket

            st.markdown(ticket_service.generate_ticket_html(t_info, lang=st.session_state.lang), unsafe_allow_html=True)
            
            # Xuất PDF in nhiệt 80mm
            pdf_bytes = ticket_service.generate_ticket_pdf(t_info, lang=st.session_state.lang)
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.download_button(
                    "📥 Tải PDF (In nhiệt 80mm)",
                    data=pdf_bytes,
                    file_name=f"PhieuKham_{t_info['ticket_number']}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
            with col_t2:
                if st.button("🗺️ Chỉ đường 3D", use_container_width=True, key="btn_go_map_after_quick_ticket"):
                    st.session_state.active_menu = "Bản đồ 3D"
                    st.session_state.target_floor = t_info["floor"]
                    st.session_state.target_dept = t_info["room_name"]
                    st.rerun()

            st.write("")
            st.info("⏳ **Kiosk Tiếp Đón:** Màn hình sẽ tự động làm mới sau 45s để đón người tiếp theo.")
            if st.button("🔄 Đón Lượt Kế Tiếp (Reset Kiosk)", use_container_width=True, type="secondary", key="btn_reset_kiosk_quick"):
                st.session_state.last_ticket = None
                st.session_state.patient_mpi_found = None
                st.session_state.patient_name_val = ""
                st.session_state.patient_phone_val = ""
                st.session_state.patient_cccd_val = ""
                st.rerun()

        else:
            # Sơ đồ Mini 3D và Định vị phòng khám dự kiến
            st.markdown("""
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <b style="font-size:0.88rem;color:#003a70;">📍 Vị trí phòng khám dự kiến trên bản đồ:</b>
            </div>
            """, unsafe_allow_html=True)
            
            mini_map_html = get_hospital_3d_html(target_floor=2 if "tim" in st.session_state.selected_booking_dept.lower() else 1, target_dept=st.session_state.selected_booking_dept, mode="mini")
            components.html(mini_map_html, height=220)
            
            if st.button("🔍 Xem bản đồ lớn 360°", use_container_width=True, key="btn_view_full_map_from_quick_book"):
                st.session_state.active_menu = "Bản đồ 3D"
                st.session_state.target_floor = 2 if "tim" in st.session_state.selected_booking_dept.lower() else 1
                st.session_state.target_dept = st.session_state.selected_booking_dept
                st.rerun()

            # Khối Tra Cứu Hồ Sơ Bệnh Nhân (Patient Master Index - MPI)
            st.markdown("""
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin-top:14px;">
                <b style="font-size:0.88rem;color:#003a70;display:block;margin-bottom:6px;">🔍 Tra cứu hồ sơ bệnh nhân cũ (MPI)</b>
                <p style="font-size:0.8rem;color:#64748b;margin:0 0 8px 0;">Nhập số CCCD / Mã BHYT / SĐT để hệ thống tự động điền thông tin và liên kết lịch sử khám.</p>
            """, unsafe_allow_html=True)
            
            c_mpi1, c_mpi2 = st.columns([72, 28])
            with c_mpi1:
                mpi_lookup_input = st.text_input("CCCD/BHYT/SĐT", value=st.session_state.patient_cccd_val, placeholder="Nhập CCCD hoặc SĐT...", label_visibility="collapsed")
            with c_mpi2:
                btn_find_mpi_act = st.button("Tìm hồ sơ", use_container_width=True, key="btn_quick_find_mpi")

            if btn_find_mpi_act and mpi_lookup_input.strip():
                st.session_state.patient_cccd_val = mpi_lookup_input.strip()
                try:
                    conn = db.get_db_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT id, patient_code, full_name, phone, cccd, dob, gender
                        FROM patients
                        WHERE cccd = ? OR bhyt_code = ? OR phone = ?
                    """, (mpi_lookup_input.strip(), mpi_lookup_input.strip(), mpi_lookup_input.strip()))
                    p_row = cur.fetchone()
                    conn.close()
                    if p_row:
                        st.session_state.patient_mpi_found = p_row[1]
                        st.session_state.patient_name_val = p_row[2]
                        st.session_state.patient_phone_val = p_row[3]
                        st.success(f"✨ Tìm thấy: **{p_row[2]}** (Mã MPI: **{p_row[1]}**)")
                        st.rerun()
                    else:
                        st.info("Chưa có hồ sơ cũ. Hệ thống sẽ tự động cấp Mã Bệnh Nhân Mới (MPI).")
                except Exception as err:
                    st.error(f"Lỗi tra cứu: {err}")

            if st.session_state.patient_mpi_found:
                st.markdown(f"<div style='font-size:0.82rem;color:#059669;font-weight:700;margin-top:6px;'>👤 Đã nhận diện hồ sơ: {st.session_state.patient_mpi_found}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# TRANG 3: TƯ VẤN SỨC KHỎE AI (CHÍNH XÁC MOCKUP 3)
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_menu == "Tư vấn AI":
    st.markdown("""
    <div class="page-title-row">
        <div>
            <h2 class="page-title-text">TƯ VẤN SỨC KHỎE AI (AI HEALTH CONSULTANT)</h2>
            <div class="page-subtitle-text">Trực tuyến & Sẵn sàng hỗ trợ 24/7 với mô hình Y tế Chuyên sâu</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_chat, c_side = st.columns([68, 32], gap="medium")

    with c_chat:
        # Cửa sổ tin nhắn trò chuyện (Stream chat chuẩn mockup 3)
        chat_container = st.container(height=360)
        with chat_container:
            # Lời chào ban đầu của AI (chuẩn mockup)
            st.markdown("""
            <div class="chat-bubble-row">
                <div class="chat-bubble-avatar" style="background:#e0f2fe;">🤖</div>
                <div class="chat-bubble-content">
                    <b>Bác sĩ Trí tuệ Nhân tạo:</b><br>
                    Chào bạn! Tôi là Bác sĩ Trí tuệ Nhân tạo của Bệnh Viện ATus. Bạn đang gặp vấn đề gì về sức khỏe hay cần tôi tư vấn điều gì không?
                </div>
            </div>
            """, unsafe_allow_html=True)

            if not st.session_state.messages:
                # Mockup câu mẫu để khớp y hệt ảnh 3 nếu chưa chat
                st.markdown("""
                <div class="chat-bubble-row">
                    <div class="chat-bubble-user-content">
                        Tôi bị đau đầu, chóng mặt từ sáng nay, hơi sốt nhẹ.
                    </div>
                    <div class="chat-bubble-avatar" style="background:#008f88;color:#fff;">👤</div>
                </div>
                <div class="chat-bubble-row">
                    <div class="chat-bubble-avatar" style="background:#e0f2fe;">🤖</div>
                    <div class="chat-bubble-content">
                        Dựa trên triệu chứng <b>đau đầu, chóng mặt và sốt nhẹ</b> của bạn, có thể bạn đang bị cảm cúm hoặc mệt mỏi do thay đổi thời tiết. Tuy nhiên, nếu có thêm các dấu hiệu như buồn nôn hay gáy cứng, bạn nên đi khám sớm. Tôi khuyến nghị bạn nên đặt lịch khám tại <b>Khoa Nội tổng quát</b> hoặc <b>Khoa Thần kinh</b> để được bác sĩ kiểm tra kỹ hơn.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                for m in st.session_state.messages:
                    if m["role"] == "user":
                        st.markdown(f"""
                        <div class="chat-bubble-row">
                            <div class="chat-bubble-user-content">{m['content']}</div>
                            <div class="chat-bubble-avatar" style="background:#008f88;color:#fff;">👤</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="chat-bubble-row">
                            <div class="chat-bubble-avatar" style="background:#e0f2fe;">🤖</div>
                            <div class="chat-bubble-content">{m['content']}</div>
                        </div>
                        """, unsafe_allow_html=True)

        # Nút hành động nhanh bên dưới câu trả lời của AI (khớp mockup)
        st.write("")
        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("👉 Đặt lịch khám Khoa Nội", use_container_width=True, type="primary"):
                st.session_state.active_menu = "Đặt lịch hẹn"
                st.session_state.selected_booking_dept = "Khoa Nội tổng quát"
                st.rerun()
        with c_act2:
            if st.button("🗺️ Xem vị trí phòng khám trên bản đồ", use_container_width=True):
                st.session_state.active_menu = "Bản đồ 3D"
                st.session_state.target_floor = 3
                st.session_state.target_dept = "Khoa Nội Tổng Quát"
                st.rerun()

        # Gợi ý Câu hỏi (Chips)
        st.markdown("<div style='font-size:0.84rem;font-weight:700;color:#003a70;margin:12px 0 6px 0;'>Gợi ý Câu hỏi</div>", unsafe_allow_html=True)
        col_cp1, col_cp2, col_cp3, col_cp4 = st.columns(4)
        quick_input = None
        with col_cp1:
            if st.button("Tôi bị đau dạ dày phải làm sao?", use_container_width=True, key="cp1"):
                quick_input = "Tôi bị đau dạ dày phải làm sao?"
        with col_cp2:
            if st.button("Tư vấn chế độ ăn tiểu đường", use_container_width=True, key="cp2"):
                quick_input = "Tư vấn chế độ ăn cho người tiểu đường"
        with col_cp3:
            if st.button("Chuẩn bị trước xét nghiệm máu", use_container_width=True, key="cp3"):
                quick_input = "Cần chuẩn bị gì trước khi xét nghiệm máu?"
        with col_cp4:
            if st.button("Tác dụng phụ của thuốc", use_container_width=True, key="cp4"):
                quick_input = "Hỏi về tác dụng phụ của thuốc"

        # Thanh nhập tin nhắn kèm nút Voice và Nút Gửi
        with st.form("form_chat_ai_consult", clear_on_submit=True):
            c_inp, c_mic, c_send = st.columns([8, 1, 1])
            with c_inp:
                user_text = st.text_input("Chat Input", placeholder="Nhập triệu chứng hoặc câu hỏi của bạn tại đây...", label_visibility="collapsed")
            with c_mic:
                st.markdown("<div style='text-align:center;font-size:20px;padding-top:4px;' title='Nói tiếng Việt'>🎙️</div>", unsafe_allow_html=True)
            with c_send:
                btn_send = st.form_submit_button("🚀", use_container_width=True, type="primary")

            if (btn_send and user_text.strip()) or quick_input:
                final_q = quick_input if quick_input else user_text.strip()
                st.session_state.messages.append({"role": "user", "content": final_q})
                
                with st.spinner("Bác sĩ AI đang phân tích dữ liệu chuyên khoa..."):
                    try:
                        reply = answer(final_q, history=st.session_state.messages[:-1])
                        txt = reply.get("text", "")
                        if not txt:
                            txt = "Dạ, Bác sĩ AI ATus đã tiếp nhận thông tin. Vui lòng kiểm tra huyết áp và đến Khoa Nội Tổng Quát để được bác sĩ khám chi tiết."
                        st.session_state.messages.append({"role": "assistant", "content": txt})
                    except Exception as err:
                        st.session_state.messages.append({"role": "assistant", "content": f"Bác sĩ AI ATus đã ghi nhận câu hỏi. Vui lòng gọi 024.7777.9999 để được hỗ trợ chuyên sâu."})
                st.rerun()

    with c_side:
        # Mini Map Card
        st.markdown("<b style='font-size:0.86rem;color:#003a70;'>Vị trí khoa gợi ý:</b>", unsafe_allow_html=True)
        mini_map_html = get_hospital_3d_html(target_floor=3, target_dept="Khoa Nội", mode="mini")
        components.html(mini_map_html, height=175)
        if st.button("🔍 Xem bản đồ lớn", use_container_width=True, key="btn_view_map_ai_side"):
            st.session_state.active_menu = "Bản đồ 3D"
            st.session_state.target_floor = 3
            st.session_state.target_dept = "Khoa Nội"
            st.rerun()

        # Thẻ Hướng Dẫn & Lưu Ý Trước Khi Khám (Không lặp form đặt lịch)
        st.markdown("""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin-top:12px;">
            <b style="font-size:0.88rem;color:#003a70;display:block;margin-bottom:6px;">📋 Lưu ý chuẩn bị trước khi khám</b>
            <ul style="font-size:0.8rem;color:#475569;margin:0;padding-left:16px;line-height:1.55;">
                <li>Mang theo CCCD gắn chip hoặc thẻ BHYT để tích hợp hồ sơ.</li>
                <li>Nhịn ăn sáng nếu bác sĩ chỉ định xét nghiệm sinh hóa máu hoặc nội soi tiêu hóa.</li>
                <li>Đến trước giờ hẹn 10 - 15 phút để lấy số ưu tiên tại Kiosk.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        # Popup "ĐẶT LỊCH NHANH THEO KHUYẾN NGHỊ AI" (Khớp chính xác mockup 3)
        st.markdown("""
        <div class="floating-ai-box" style="margin-top:12px;">
            <div class="floating-ai-header">
                <span>GỢI Ý KHOA KHÁM TỪ BÁC SĨ AI</span>
            </div>
            <div class="floating-ai-body">
                <div style="font-weight:700;color:#008f88;font-size:0.82rem;margin-bottom:4px;">Chuyên khoa gợi ý: Khoa Nội tổng quát</div>
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;">
                    <div class="doc-avatar">👨‍⚕️</div>
                    <div>
                        <b style="font-size:0.84rem;color:#0f172a;">BS. Nguyễn Tấn</b><br>
                        <span style="font-size:0.75rem;color:#64748b;">Trưởng Khoa Nội tổng quát</span><br>
                        <span style="font-size:0.75rem;color:#eab308;">⭐⭐⭐⭐⭐ 5.0</span>
                    </div>
                </div>
                <div style="font-size:0.78rem;color:#64748b;margin-bottom:4px;">Khung giờ trống sớm nhất: <b>08:00 - 09:00 - 10:00</b></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Đặt Lịch Hẹn Tại Khoa Này", use_container_width=True, type="primary", key="btn_confirm_ai_rec"):
            st.session_state.active_menu = "Đặt lịch hẹn"
            st.session_state.selected_booking_dept = "Khoa Nội"
            st.session_state.selected_booking_doc = "BS. Nguyễn Tấn"
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# TRANG 4: LỊCH SỬ KHÁM BỆNH (CHÍNH XÁC MOCKUP 2)
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_menu == "Lịch sử khám":
    st.markdown("""
    <div class="page-title-row">
        <div>
            <h2 class="page-title-text">LỊCH SỬ KHÁM BỆNH</h2>
            <div class="page-subtitle-text">Bệnh nhân: <b>Nguyễn Văn A</b> - Mã BN: <b>BN123456</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c_hist, c_side = st.columns([68, 32], gap="medium")

    with c_hist:
        c_filter, c_cards = st.columns([30, 70], gap="small")

        with c_filter:
            st.markdown("""
            <div class="white-card">
                <b style="font-size:0.88rem;color:#003a70;display:block;margin-bottom:8px;">Thời gian</b>
                <div style="background:#008f88;color:#fff;padding:6px 12px;border-radius:20px;font-size:0.8rem;font-weight:700;display:inline-block;margin-bottom:6px;">Tất cả</div><br>
                <div style="color:#64748b;font-size:0.8rem;padding:4px 0;">3 tháng gần nhất</div>
                <div style="color:#64748b;font-size:0.8rem;padding:4px 0;">1 năm gần đây</div>
                <hr style="margin:10px 0;border:0;border-top:1px solid #f1f5f9;">
                <b style="font-size:0.88rem;color:#003a70;display:block;margin-bottom:8px;">Trạng thái</b>
                <div style="font-size:0.82rem;color:#0f172a;margin-bottom:4px;">🟢 <b>Đã khám</b></div>
                <div style="font-size:0.82rem;color:#64748b;margin-bottom:4px;">⚪ Chờ khám</div>
                <div style="font-size:0.82rem;color:#64748b;">⚪ Đã hủy</div>
            </div>
            """, unsafe_allow_html=True)

        with c_cards:
            # Header Lượt khám 1
            st.markdown("""
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <b style="color:#003a70;font-size:0.9rem;">Lượt khám 1 (Gần nhất)</b>
                <span style="font-size:0.8rem;color:#008f88;cursor:pointer;font-weight:600;">📍 Đường đi từ cổng</span>
            </div>
            """, unsafe_allow_html=True)

            # Thẻ 1: Khám Nội tổng quát
            st.markdown("""
            <div class="history-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b style="font-size:0.95rem;color:#0f172a;">Khám Nội tổng quát</b>
                    <span style="font-size:0.8rem;color:#64748b;">Ngày 10/11/2026</span>
                </div>
                <div style="font-size:0.82rem;color:#64748b;margin:4px 0;">Bác sĩ: <b>PGS.TS. Nguyễn Văn A</b></div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <span style="font-size:0.8rem;color:#64748b;">Mã hồ sơ: <b>50123450</b></span>
                    <span class="badge-status-done">Đã hoàn thành</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                st.button("Xem kết luận & Đơn thuốc", use_container_width=True, type="primary", key="btn_h1_pres")
            with col_b2:
                st.button("Xem hóa đơn", use_container_width=True, key="btn_h1_bill")
            with col_b3:
                st.button("Đặt lại lịch", use_container_width=True, key="btn_h1_rebook")

            st.write("")
            # Thẻ 2: Khám Tai Mũi Họng
            st.markdown("""
            <div class="history-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b style="font-size:0.95rem;color:#0f172a;">Khám Tai Mũi Họng</b>
                    <span style="font-size:0.8rem;color:#64748b;">Ngày 25/10/2026</span>
                </div>
                <div style="font-size:0.82rem;color:#64748b;margin:4px 0;">Bác sĩ: <b>BSCKI. Lê Thị B</b></div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <span style="font-size:0.8rem;color:#64748b;">Chẩn đoán: <b>Viêm họng cấp (Số 50 006)</b></span>
                    <span class="badge-status-done">Đã hoàn thành</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col_b2_1, col_b2_2 = st.columns(2)
            with col_b2_1:
                st.button("Xem bệnh án", use_container_width=True, key="btn_h2_rec")
            with col_b2_2:
                st.button("Đơn thuốc", use_container_width=True, key="btn_h2_pres")

            st.write("")
            # Thẻ 3: Xét nghiệm máu & Siêu âm
            st.markdown("""
            <div class="history-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b style="font-size:0.95rem;color:#0f172a;">Xét nghiệm máu & Siêu âm</b>
                    <span style="font-size:0.8rem;color:#64748b;">Ngày 12/09/2026</span>
                </div>
                <div style="font-size:0.82rem;color:#64748b;margin:4px 0;">Bác sĩ: <b>BSCKII. Trần C</b></div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <span style="font-size:0.8rem;color:#64748b;">Kết luận: <b>Rối loạn tiêu hóa</b></span>
                    <span class="badge-status-done">Đã hoàn thành</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.button("📄 Tải kết quả (PDF)", use_container_width=True, key="btn_h3_pdf")

    with c_side:
        # Mini 3D Map
        st.markdown("<b style='font-size:0.86rem;color:#003a70;'>Phòng khám Nội số 3, Tầng 1:</b>", unsafe_allow_html=True)
        mini_map_html = get_hospital_3d_html(target_floor=1, target_dept="Phòng khám Nội số 3", mode="mini")
        components.html(mini_map_html, height=175)
        if st.button("🔍 Xem bản đồ lớn", use_container_width=True, key="btn_view_map_from_hist"):
            st.session_state.active_menu = "Bản đồ 3D"
            st.session_state.target_floor = 1
            st.session_state.target_dept = "Phòng khám Nội số 3"
            st.rerun()

        # Thẻ "Lượt khám sắp tới" (chuẩn mockup 2)
        st.markdown("""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin-top:10px;">
            <b style="font-size:0.88rem;color:#003a70;display:block;margin-bottom:6px;">Lượt khám sắp tới:</b>
            <div style="font-size:0.92rem;font-weight:700;color:#0f172a;">Khám Răng Hàm Mặt</div>
            <div style="font-size:0.8rem;color:#64748b;margin-bottom:12px;">⏰ 09:00 ngày 15/11/2026 (Phòng 303, Tầng 3)</div>
        """, unsafe_allow_html=True)
        if st.button("🧭 Xem hướng dẫn di chuyển", use_container_width=True, type="primary"):
            st.session_state.active_menu = "Bản đồ 3D"
            st.session_state.target_floor = 3
            st.session_state.target_dept = "Khoa Tai Mũi Họng & Mắt"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# TRANG 5: TRANG CHỦ & CÀI ĐẶT
# ═══════════════════════════════════════════════════════════════════════════
elif st.session_state.active_menu == "Trang chủ":
    st.markdown("""
    <div style="background:linear-gradient(135deg, #003a70 0%, #008f88 100%);color:white;padding:24px 28px;border-radius:14px;margin-bottom:20px;">
        <h2 style="margin:0 0 8px 0;color:white;font-weight:800;">Chào mừng quý khách đến với BỆNH VIỆN ATUS</h2>
        <p style="margin:0;opacity:0.92;font-size:0.95rem;">Hệ thống y tế thông minh tích hợp Trợ lý Trí tuệ Nhân tạo & Bản đồ 3D chỉ dẫn phân khoa hàng đầu.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""
        <div class="white-card">
            <div style="font-size:28px;">🗺️</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Bản đồ 3D Tầng</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Mặt bằng Isometric trực quan, tìm kiếm phòng khám dễ dàng.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Xem Bản Đồ 3D", use_container_width=True, key="home_btn_map"):
            st.session_state.active_menu = "Bản đồ 3D"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="white-card">
            <div style="font-size:28px;">📅</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Đặt Lịch & Cấp Số</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Lấy số thứ tự trực tiếp, gửi SMS xác nhận tức thì.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Đặt Lịch Ngay", use_container_width=True, key="home_btn_book"):
            st.session_state.active_menu = "Đặt lịch hẹn"
            st.rerun()

    with c3:
        st.markdown("""
        <div class="white-card">
            <div style="font-size:28px;">🤖</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Bác Sĩ AI Tiếp Đón</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Hỏi đáp triệu chứng, quy trình BHYT và định vị phòng.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Chat Với Bác Sĩ AI", use_container_width=True, key="home_btn_ai"):
            st.session_state.active_menu = "Tư vấn AI"
            st.rerun()

    with c4:
        st.markdown("""
        <div class="white-card">
            <div style="font-size:28px;">🕒</div>
            <div style="font-weight:700;font-size:1.05rem;color:#003a70;margin-top:6px;">Tra Cứu Lịch Sử</div>
            <p style="font-size:0.82rem;color:#64748b;margin:4px 0 12px 0;">Xem mã phiếu, thời gian chờ và tiến độ khám tại các phòng.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👉 Tra Cứu Lịch Sử", use_container_width=True, key="home_btn_hist"):
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

elif st.session_state.active_menu == "Cài đặt":
    st.markdown("""
    <div class="page-title-row">
        <div>
            <h2 class="page-title-text">⚙️ CÀI ĐẶT HỆ THỐNG KIOSK BỆNH VIỆN ATUS</h2>
        </div>
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
        st.info("Trạng thái cơ sở dữ liệu: **Microsoft SQL Server `hospital_atus` (Đã đồng bộ)**")


# ═══════════════════════════════════════════════════════════════════════════
# FLOATING AI ASSISTANT POPUP (FAB WIDGET NỔI GÓC PHẢI DƯỚI TOÀN HỆ THỐNG)
# ═══════════════════════════════════════════════════════════════════════════
# Thiết kế dạng Popover nổi (Fixed FAB) - KHÔNG chiếm diện tích cột layout hay mô hình 3D!
with st.container():
    with st.popover("💬 🤖 AI Assistant (Tư vấn 24/7)", help="Bác sĩ AI hỗ trợ chỉ đường, hướng dẫn BHYT và giải đáp sức khỏe"):
        st.markdown("""
        <div style="border-bottom:1px solid #e2e8f0;padding-bottom:8px;margin-bottom:10px;display:flex;align-items:center;gap:10px;">
            <div style="width:36px;height:36px;border-radius:50%;background:#008f88;color:white;display:flex;align-items:center;justify-content:center;font-size:20px;">🤖</div>
            <div>
                <b style="color:#003a70;font-size:0.95rem;display:block;">Bác Sĩ Trí Tuệ Nhân Tạo ATUS</b>
                <span style="font-size:0.75rem;color:#059669;font-weight:600;">● Trực tuyến 24/7 · Sẵn sàng hỗ trợ</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not st.session_state.messages:
            st.markdown("""
            <div style="background:#f0fdfa;border:1px solid #ccfbf1;border-radius:10px;padding:10px;font-size:0.84rem;color:#0f766e;margin-bottom:10px;">
                👋 <b>Xin chào bạn!</b> Tôi là Trợ lý AI Bệnh Viện ATUS. Bạn đang gặp phải triệu chứng gì hay cần tìm phòng khám nào?
            </div>
            """, unsafe_allow_html=True)
        else:
            with st.container(height=260):
                for m in st.session_state.messages[-6:]:
                    if m["role"] == "user":
                        st.markdown(f"""
                        <div style="background:#008f88;color:#ffffff;border-radius:12px;padding:8px 12px;font-size:0.83rem;margin:6px 0 6px auto;max-width:85%;text-align:right;">
                            {m["content"]}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="background:#f1f5f9;color:#1e293b;border-radius:12px;padding:8px 12px;font-size:0.83rem;margin:6px auto 6px 0;max-width:85%;">
                            <b>AI:</b> {m["content"]}
                        </div>
                        """, unsafe_allow_html=True)

        st.markdown("<span style='font-size:0.78rem;font-weight:700;color:#64748b;'>Gợi ý nhanh:</span>", unsafe_allow_html=True)
        ch1, ch2 = st.columns(2)
        with ch1:
            if st.button("Đau đầu chóng mặt", key="fab_q1", use_container_width=True):
                st.session_state.fab_input_val = "Tôi bị đau đầu, chóng mặt từ sáng nay"
                st.rerun()
        with ch2:
            if st.button("Khám Nội ở phòng nào?", key="fab_q2", use_container_width=True):
                st.session_state.fab_input_val = "Tôi muốn khám Nội thì đi phòng nào?"
                st.rerun()

        with st.form("form_fab_ai_chat", clear_on_submit=True):
            fab_txt = st.text_input("Câu hỏi của bạn:", value=st.session_state.get("fab_input_val", ""), placeholder="Nhập triệu chứng hoặc phòng khám...", label_visibility="collapsed")
            col_s1, col_s2 = st.columns([75, 25])
            with col_s1:
                submit_fab = st.form_submit_button("Gửi tin 🚀", use_container_width=True, type="primary")
            with col_s2:
                clear_fab = st.form_submit_button("Xóa", use_container_width=True)

            if clear_fab:
                st.session_state.messages = []
                st.session_state.fab_input_val = ""
                st.rerun()

            if submit_fab and fab_txt.strip():
                user_msg = fab_txt.strip()
                st.session_state.fab_input_val = ""
                st.session_state.messages.append({"role": "user", "content": user_msg})

                low_msg = user_msg.lower()
                # Triage red-flag safety check
                if any(w in low_msg for w in ["đau ngực", "khó thở", "liệt", "ngất", "bất tỉnh", "co giật", "tai biến", "đột quỵ"]):
                    ans = "🚨 CẢNH BÁO NGUY CƠ CẤP CỨU CAO: Vui lòng đến ngay Khoa Cấp Cứu (P.101, Tầng 1) hoặc báo nhân viên y tế gần nhất ngay lập tức!"
                    st.session_state.target_floor = 1
                    st.session_state.target_dept = "Khoa Cấp Cứu 24/7"
                else:
                    ans = answer(user_msg)
                    if "nội" in low_msg:
                        st.session_state.target_floor = 1
                        st.session_state.target_dept = "Khoa Khám Bệnh Chung"
                    elif "nhi" in low_msg:
                        st.session_state.target_floor = 1
                        st.session_state.target_dept = "Khoa Khám Nhi"
                    elif "tai mũi họng" in low_msg or "mắt" in low_msg:
                        st.session_state.target_floor = 3
                        st.session_state.target_dept = "Khoa Tai Mũi Họng & Mắt"

                st.session_state.messages.append({"role": "assistant", "content": ans})
                st.rerun()

"""Trang 3: CỔNG QUẢN TRỊ VIÊN & TRƯỞNG KHOA (ADMIN ONLY)
- Dành riêng cho Quản Trị Hệ Thống (admin) và Trưởng Khoa (manager).
- Dashboard giám sát hàng đợi toàn bộ 12 phòng khám & phòng cận lâm sàng thời gian thực.
- Thống kê phân tích số liệu (Analytics, Intent, Chuyên khoa, Cảnh báo khẩn cấp).
- Quản lý danh sách tài khoản nhân viên y tế (Users & Roles).
- Nhật ký kiểm toán an toàn y tế (Audit Trail).
Chạy ứng dụng:
    streamlit run app_admin.py --server.port 8503
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import db
import queue_service
import auth
from analytics import get_analytics_summary

st.set_page_config(
    page_title="Cổng Quản Trị Hệ Thống - Bệnh Viện ATus",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "admin_user" not in st.session_state:
    st.session_state.admin_user = None

user = st.session_state.admin_user

# ═══════════════════════════════════════════════════════════════════════════
# MÀN HÌNH ĐĂNG NHẬP ADMIN (NẾU CHƯA ĐĂNG NHẬP)
# ═══════════════════════════════════════════════════════════════════════════
if not user:
    col_l, col_center, col_r = st.columns([3, 4, 3])
    with col_center:
        st.write("")
        st.write("")
        st.markdown("""
        <div style="text-align:center;margin-bottom:20px;">
            <h2 style="color:#0f172a;margin-bottom:4px;">🔐 CỔNG QUẢN TRỊ HỆ THỐNG</h2>
            <p style="color:#64748b;margin:0;">Bệnh Viện Đa Khoa ATus</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("admin_login_form"):
            uname = st.text_input("Tài khoản quản trị *", placeholder="admin hoặc qly_khoanoi")
            pwd = st.text_input("Mật khẩu *", type="password")
            btn_log = st.form_submit_button("Đăng Nhập Vào Trung Tâm Quản Trị", use_container_width=True, type="primary")

            if btn_log:
                if not uname.strip() or not pwd:
                    st.error("Vui lòng điền đầy đủ thông tin đăng nhập!")
                else:
                    res = auth.authenticate_user(uname.strip(), pwd)
                    if res["success"]:
                        u_data = res["user"]
                        if u_data["role"] not in ("admin", "manager"):
                            st.error(f"⛔ Tài khoản của bạn không có quyền Quản trị (Vai trò: {u_data['role']}).")
                        else:
                            st.session_state.admin_user = u_data
                            st.rerun()
                    else:
                        st.error(res["error"])

        st.markdown("""
        ---
        **💡 Tài khoản mẫu quản trị:**
        - **Admin toàn quyền:** `admin` / `admin123`
        - **Trưởng khoa Nội:** `qly_khoanoi` / `123456`
        """)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# MAIN DASHBOARD QUẢN TRỊ
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"### ⚙️ {user['full_name']}")
    st.markdown(f"**Quyền hạn:** `{user['role'].upper()}`")
    st.markdown(f"**Khoa:** {user['department_name'] or 'Toàn bệnh viện'}")
    st.write("---")
    if st.button("🚪 Đăng Xuất Quản Trị", use_container_width=True):
        auth.log_audit(user["id"], user["username"], "LOGOUT", "USER", str(user["id"]), "Admin đăng xuất")
        st.session_state.admin_user = None
        st.rerun()

st.markdown("""
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <h2 style="margin:0;color:#0f172a;">📊 Trung Tâm Quản Trị & Giám Sát Bệnh Viện ATus</h2>
    <span style="background:#dcfce7;color:#166534;padding:4px 12px;border-radius:20px;font-weight:700;font-size:0.85rem;">Live Active</span>
</div>
""", unsafe_allow_html=True)

tab_kpi, tab_queues, tab_users, tab_audit = st.tabs([
    "📈 Báo Cáo & KPI", "🏥 Giám Sát Hàng Đợi Toàn Viện", "👥 Quản Lý Người Dùng", "📜 Nhật Ký Audit Log"
])

# ── TAB 1: KPI & ANALYTICS ──────────────────────────────────────────────────
with tab_kpi:
    summary = get_analytics_summary()
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE visit_date = CAST(GETDATE() AS DATE)")
    today_tickets = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM clinical_orders WHERE CAST(created_at AS DATE) = CAST(GETDATE() AS DATE)")
    today_orders = cursor.fetchone()[0]
    conn.close()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Lượt hỏi đáp AI Kiosk", summary["total_queries"])
    m2.metric("Số lượt cấp vé hôm nay", today_tickets)
    m3.metric("Chỉ định cận lâm sàng", today_orders)
    m4.metric("Cảnh báo khẩn cấp AI", summary["emergency_count"])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Phân bố Ý định (Intent) Bệnh nhân")
        if summary["intent_counts"]:
            st.bar_chart(summary["intent_counts"])
        else:
            st.info("Chưa có đủ dữ liệu tương tác.")
    with c2:
        st.subheader("Khoa phòng được quan tâm nhiều nhất")
        if summary["dept_counts"]:
            st.bar_chart(summary["dept_counts"])
        else:
            st.info("Chưa có đủ dữ liệu.")

# ── TAB 2: GIÁM SÁT HÀNG ĐỢI TOÀN VIỆN ──────────────────────────────────────
with tab_queues:
    st.subheader("🏥 Tình Trạng Hàng Đợi Thời Gian Thực Các Phòng")
    all_rooms = queue_service.get_all_rooms()
    room_cols = st.columns(3)
    for idx, r in enumerate(all_rooms):
        q = queue_service.get_room_queue(r["id"])
        with room_cols[idx % 3]:
            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="font-weight:700;color:#0284c7;">{r['room_number']} - {r['name']}</div>
                <div style="font-size:0.8rem;color:#64748b;">Tầng {r['floor']} | Loại: {r['type'].upper()}</div>
                <div style="margin-top:8px;display:flex;justify-content:space-between;">
                    <span>Đang gọi: <b>{len(q['calling'])}</b></span>
                    <span>Đang khám: <b>{len(q['in_progress'])}</b></span>
                    <span style="color:#dc2626;">Đang chờ: <b>{q['total_waiting']}</b></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ── TAB 3: QUẢN LÝ NGƯỜI DÙNG ───────────────────────────────────────────────
with tab_users:
    st.subheader("👥 Danh Sách Tài Khoản Nhân Viên Hệ Thống")
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.full_name, u.role, d.name as dept_name, r.name as room_name,
               u.is_active, u.failed_login_count, u.created_at
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN rooms r ON u.room_id = r.id
        ORDER BY u.id ASC
    """)
    cols = [column[0] for column in cursor.description]
    users_data = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    if users_data:
        df_users = pd.DataFrame(users_data)
        st.dataframe(df_users, use_container_width=True)

# ── TAB 4: AUDIT LOGS ───────────────────────────────────────────────────────
with tab_audit:
    st.subheader("📜 Nhật Ký Kiểm Toán An Toàn Y Tế (Audit Trail)")
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP 100 id, username, action, target_type, target_id, details, ip_address, created_at
        FROM audit_logs
        ORDER BY id DESC
    """)
    cols = [column[0] for column in cursor.description]
    audit_data = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()

    if audit_data:
        df_audit = pd.DataFrame(audit_data)
        st.dataframe(df_audit, use_container_width=True)
    else:
        st.info("Chưa có bản ghi audit log nào.")

st.write("---")
if st.button("🔄 Làm mới dữ liệu quản trị"):
    st.rerun()

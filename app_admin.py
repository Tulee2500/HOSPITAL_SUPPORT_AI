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

# ── TAB 3: QUẢN LÝ CÁN BỘ NHÂN VIÊN & PHÂN CA ──────────────────────────────
with tab_users:
    st.subheader("👥 Quản Lý Cán Bộ Nhân Viên & Lịch Phân Ca Bệnh Viện ATus")
    
    # Lấy danh sách toàn bộ cán bộ nhân viên
    all_staff = auth.get_all_staff_users()
    all_depts = auth.get_all_departments()
    all_rooms = queue_service.get_all_rooms()

    # Thống kê nhanh số lượng nhân sự
    total_staff = len(all_staff)
    total_docs = sum(1 for u in all_staff if u["role"] == "doctor")
    total_nurses = sum(1 for u in all_staff if u["role"] == "nurse")
    total_techs = sum(1 for u in all_staff if u["role"] == "technician")
    total_others = total_staff - (total_docs + total_nurses + total_techs)

    kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5 = st.columns(5)
    kpi_c1.metric("Tổng Nhân Sự", f"{total_staff} người")
    kpi_c2.metric("Bác Sĩ", f"{total_docs} BS")
    kpi_c3.metric("Điều Dưỡng / Y Tá", f"{total_nurses} ĐD")
    kpi_c4.metric("Kỹ Thuật Viên CLS", f"{total_techs} KTV")
    kpi_c5.metric("Khối Hỗ Trợ & Quản Lý", f"{total_others} người")

    st.write("")

    sub_u1, sub_u2, sub_u3, sub_u4 = st.tabs([
        "📋 Danh Sách Cán Bộ",
        "➕ Thêm Cán Bộ Mới",
        "📅 Phân Công Ca Trực",
        "🗓️ Lịch Trực Bác Sĩ Toàn Viện"
    ])

    # 1. DANH SÁCH CÁN BỘ NHÂN VIÊN
    with sub_u1:
        c_filter1, c_filter2 = st.columns([40, 60])
        with c_filter1:
            role_options = ["Tất cả vai trò", "doctor (Bác sĩ)", "nurse (Điều dưỡng)", "technician (Kỹ thuật viên)", "manager (Trưởng khoa)", "cashier (Thu ngân)", "pharmacist (Dược sĩ)", "admin (Quản trị viên)"]
            sel_role_filter = st.selectbox("Lọc theo vai trò:", options=role_options)
        with c_filter2:
            search_staff_text = st.text_input("🔍 Tìm kiếm theo tên hoặc username:", placeholder="Nhập tên bác sĩ, điều dưỡng...")

        filtered_staff = all_staff
        if "Tất cả" not in sel_role_filter:
            role_code = sel_role_filter.split()[0]
            filtered_staff = [u for u in filtered_staff if u["role"] == role_code]
        if search_staff_text.strip():
            kw = search_staff_text.strip().lower()
            filtered_staff = [u for u in filtered_staff if kw in u["full_name"].lower() or kw in u["username"].lower()]

        if filtered_staff:
            df_display = pd.DataFrame([{
                "ID": u["id"],
                "Họ và Tên": u["full_name"],
                "Tài Khoản": u["username"],
                "Vai Trò": u["role"].upper(),
                "Khoa / Chuyên Khoa": u["department_name"] or "—",
                "Phòng Mặc Định": f"{u['room_code']} - {u['room_name']}" if u["room_name"] else "—",
                "Trạng Thái": "🟢 Hoạt động" if u["is_active"] else "🔴 Đã khóa",
                "Ngày Tạo": str(u["created_at"])[:10] if u["created_at"] else "—"
            } for u in filtered_staff])
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Thao tác Khóa / Mở khóa tài khoản
            with st.expander("⚙️ Thao tác khóa / mở khóa tài khoản cán bộ"):
                col_op1, col_op2, col_op3 = st.columns([50, 25, 25])
                with col_op1:
                    staff_dict = {f"{u['full_name']} ({u['username']} - {u['role']})": u for u in all_staff if u["username"] != "admin"}
                    selected_staff_label = st.selectbox("Chọn nhân viên để cập nhật trạng thái:", options=list(staff_dict.keys()))
                sel_u = staff_dict[selected_staff_label]
                with col_op2:
                    st.write("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("🔒 Khóa Tài Khoản", use_container_width=True, disabled=not sel_u["is_active"]):
                        auth.update_staff_status(sel_u["id"], is_active=False, updated_by=user["username"])
                        st.success(f"Đã tạm khóa tài khoản của {sel_u['full_name']}.")
                        st.rerun()
                with col_op3:
                    st.write("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("🔓 Mở Khóa / Kích Hoạt", use_container_width=True, disabled=bool(sel_u["is_active"])):
                        auth.update_staff_status(sel_u["id"], is_active=True, updated_by=user["username"])
                        st.success(f"Đã kích hoạt lại tài khoản của {sel_u['full_name']}.")
                        st.rerun()
        else:
            st.info("Không tìm thấy cán bộ nhân viên phù hợp với bộ lọc.")

    # 2. FORM THÊM CÁN BỘ NHÂN VIÊN MỚI
    with sub_u2:
        st.markdown("#### ➕ Tiếp Nhận & Tạo Mới Hồ Sơ Cán Bộ Nhân Viên")
        st.caption("Mật khẩu sẽ được tự động băm chuẩn Bcrypt (12 rounds) và lưu an toàn vào hệ thống. Hành động này được ghi vết Audit Log.")

        with st.form("form_create_staff"):
            c_new1, c_new2 = st.columns(2)
            with c_new1:
                new_fullname = st.text_input("Họ và tên cán bộ y tế *", placeholder="Ví dụ: BSCKII. Trần Hoàng Nam")
                new_username = st.text_input("Tên đăng nhập (Username) *", placeholder="Ví dụ: bs_nam_t105")
                new_password = st.text_input("Mật khẩu khởi tạo *", type="password", placeholder="Tối thiểu 6 ký tự")
            
            with c_new2:
                role_choices = [
                    ("doctor", "Bác sĩ điều trị / Bác sĩ lâm sàng"),
                    ("nurse", "Điều dưỡng / Y tá chăm sóc"),
                    ("technician", "Kỹ thuật viên xét nghiệm / CĐHA"),
                    ("pharmacist", "Dược sĩ nhà thuốc"),
                    ("cashier", "Thu ngân / Viện phí"),
                    ("manager", "Trưởng khoa / Quản lý chuyên môn"),
                    ("admin", "Quản trị viên hệ thống")
                ]
                sel_new_role = st.selectbox("Vai trò phân quyền (RBAC) *", options=[r[0] for r in role_choices], format_func=lambda x: dict(role_choices)[x])

                dept_choices = [(d["id"], f"{d['code']} - {d['name']} (Tầng {d['floor']})") for d in all_depts]
                dept_dict = dict(dept_choices)
                sel_dept_id = st.selectbox("Khoa / Bộ phận công tác:", options=[None] + [d[0] for d in dept_choices], format_func=lambda x: "— Không thuộc khoa cụ thể —" if x is None else dept_dict.get(x, ""))

                room_choices = [(r["id"], f"{r['code']} - {r['name']} (Tầng {r['floor']})") for r in all_rooms]
                room_dict = dict(room_choices)
                sel_room_id = st.selectbox("Phòng làm việc mặc định:", options=[None] + [r[0] for r in room_choices], format_func=lambda x: "— Không gán phòng cố định —" if x is None else room_dict.get(x, ""))

            btn_submit_create = st.form_submit_button("Xác Nhận Tạo Mới Cán Bộ Nhân Viên", use_container_width=True, type="primary")

            if btn_submit_create:
                if not new_fullname.strip() or not new_username.strip() or not new_password:
                    st.error("Vui lòng điền đầy đủ Họ tên, Username và Mật khẩu!")
                else:
                    try:
                        res_create = auth.create_staff_user(
                            username=new_username,
                            password=new_password,
                            full_name=new_fullname,
                            role=sel_new_role,
                            department_id=sel_dept_id,
                            room_id=sel_room_id,
                            created_by=user["username"]
                        )
                        st.success(f"🎉 Đã tạo thành công tài khoản: **{res_create['full_name']}** (`{res_create['username']}`) - Vai trò: **{res_create['role'].upper()}**")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Lỗi tạo tài khoản: {err}")

    # 3. PHÂN CÔNG CA TRỰC BÁC SĨ / ĐIỀU DƯỠNG
    with sub_u3:
        st.markdown("#### 📅 Xếp Lịch Phân Ca Làm Việc Theo Phòng & Buổi")
        st.caption("Gán bác sĩ/y tá vào phòng khám cụ thể trong ngày. Logic cấp số tự động tại Kiosk sẽ chỉ chuyển bệnh nhân vào phòng có bác sĩ đang trực.")

        with st.form("form_schedule_shift"):
            c_sc1, c_sc2 = st.columns(2)
            with c_sc1:
                # Chỉ lọc những người có vai trò doctor hoặc nurse
                clinical_staff = [u for u in all_staff if u["role"] in ("doctor", "nurse", "technician")]
                sc_staff_choices = [(u["id"], f"{u['full_name']} ({u['role'].upper()})") for u in clinical_staff]
                sc_staff_dict = dict(sc_staff_choices)
                sc_doctor_id = st.selectbox("Chọn bác sĩ / nhân viên y tế *", options=[s[0] for s in sc_staff_choices], format_func=lambda x: sc_staff_dict[x])

                sc_date = st.date_input("Ngày làm việc *", value=pd.to_datetime("today").date())

            with c_sc2:
                # Phòng khám
                clinic_rooms_only = [r for r in all_rooms if r["type"] in ("clinic", "paraclinical", "emergency", "inpatient")]
                sc_room_choices = [(r["id"], f"{r['code']} - {r['name']} (Tầng {r['floor']})") for r in clinic_rooms_only]
                sc_room_dict = dict(sc_room_choices)
                sc_room_id = st.selectbox("Phòng khám / Khu vực trực *", options=[r[0] for r in sc_room_choices], format_func=lambda x: sc_room_dict[x])

                shift_choices = [
                    ("morning", "Ca Sáng (07:00 – 11:30)", "07:00", "11:30"),
                    ("afternoon", "Ca Chiều (13:00 – 17:00)", "13:00", "17:00"),
                    ("night", "Ca Trực Đêm (17:00 – 07:00 sáng hôm sau)", "17:00", "07:00"),
                    ("full_day", "Trực 24/7 (Cấp Cứu / ICU)", "00:00", "23:59")
                ]
                sel_shift_idx = st.selectbox("Chọn ca làm việc *", options=range(len(shift_choices)), format_func=lambda i: shift_choices[i][1])
                chosen_shift = shift_choices[sel_shift_idx]

            btn_submit_shift = st.form_submit_button("Xác Nhận Lưu Lịch Phân Ca", use_container_width=True, type="primary")

            if btn_submit_shift:
                try:
                    res_shift = auth.schedule_staff_shift(
                        doctor_id=sc_doctor_id,
                        room_id=sc_room_id,
                        work_date=sc_date,
                        shift=chosen_shift[0],
                        start_time=chosen_shift[2],
                        end_time=chosen_shift[3],
                        max_patients=40,
                        created_by=user["username"]
                    )
                    st.success(f"🎉 Đã lưu lịch ca trực thành công (Mã phân ca: #{res_shift['schedule_id']})!")
                    st.rerun()
                except Exception as err:
                    st.error(f"Lỗi xếp ca: {err}")

    # 4. XEM LỊCH TRỰC BÁC SĨ TOÀN VIỆN
    with sub_u4:
        st.markdown("#### 🗓️ Lịch Trực Phân Ca Hôm Nay & Các Ngày Tiếp Theo")
        conn_sc = db.get_db_connection()
        cur_sc = conn_sc.cursor()
        cur_sc.execute("""
            SELECT ds.id, u.full_name AS doctor_name, u.role, r.code AS room_code, r.name AS room_name,
                   ds.work_date, ds.shift, ds.start_time, ds.end_time, ds.max_patients, ds.is_active
            FROM doctor_schedules ds
            JOIN users u ON ds.doctor_id = u.id
            JOIN rooms r ON ds.room_id = r.id
            WHERE ds.work_date >= CAST(GETDATE() AS DATE)
            ORDER BY ds.work_date ASC, ds.shift ASC, r.code ASC
        """)
        cols_sc = [c[0] for c in cur_sc.description]
        schedules_data = [dict(zip(cols_sc, row)) for row in cur_sc.fetchall()]
        conn_sc.close()

        if schedules_data:
            df_sched = pd.DataFrame([{
                "Mã Ca": s["id"],
                "Ngày": str(s["work_date"]),
                "Ca Trực": s["shift"].upper(),
                "Thời Gian": f"{s['start_time']} – {s['end_time']}",
                "Bác Sĩ / Cán Bộ": s["doctor_name"],
                "Vai Trò": s["role"].upper(),
                "Phòng Khám": f"{s['room_code']} - {s['room_name']}",
                "Giới Hạn": f"{s['max_patients']} BN"
            } for s in schedules_data])
            st.dataframe(df_sched, use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có lịch phân ca trong hôm nay và các ngày tới.")

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

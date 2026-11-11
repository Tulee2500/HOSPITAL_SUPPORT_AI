"""Trang 2: CỔNG NHÂN VIÊN Y TẾ (STAFF ONLY)
- Dành riêng cho Bác Sĩ lâm sàng và Kỹ Thuật Viên Cận Lâm Sàng.
- Yêu cầu đăng nhập tài khoản nhân viên.
- Tự động nhận diện vai trò:
    + Bác sĩ: Quản lý hàng đợi phòng khám, gọi số, chỉ định cận lâm sàng, hoàn thành khám.
    + Kỹ thuật viên: Tiếp nhận bệnh nhân được chỉ định tại phòng CLS (máu, hô hấp...), nhập kết quả và tự động trả về phòng khám ban đầu kèm cờ ưu tiên.
Chạy ứng dụng:
    streamlit run app_staff.py --server.port 8502
"""
from __future__ import annotations

import streamlit as st
import db
import queue_service
import auth

st.set_page_config(
    page_title="Cổng Nhân Viên Y Tế - Bệnh Viện ATus",
    page_icon="👨‍⚕️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .staff-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; margin-bottom: 15px; }
    .calling-box { background: #fef2f2; border: 2px solid #ef4444; border-radius: 10px; padding: 15px; margin-bottom: 15px; }
    .calling-number { font-size: 2.2rem; font-weight: 800; color: #dc2626; }
    .priority-tag { background: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.8rem; }
    .role-tag { background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

if "staff_user" not in st.session_state:
    st.session_state.staff_user = None

user = st.session_state.staff_user

# ═══════════════════════════════════════════════════════════════════════════
# MÀN HÌNH ĐĂNG NHẬP (NẾU CHƯA ĐĂNG NHẬP)
# ═══════════════════════════════════════════════════════════════════════════
if not user:
    col_l, col_center, col_r = st.columns([3, 4, 3])
    with col_center:
        st.write("")
        st.write("")
        st.markdown("""
        <div style="text-align:center;margin-bottom:20px;">
            <h2 style="color:#023e8a;margin-bottom:4px;">🏥 CỔNG NHÂN VIÊN Y TẾ</h2>
            <p style="color:#64748b;margin:0;">Bác Sĩ & Kỹ Thuật Viên Cận Lâm Sàng</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("staff_login_form"):
            uname = st.text_input("Tên đăng nhập *", placeholder="bsi_mat, bsi_noi, ktv_mau, ktv_hohap...")
            pwd = st.text_input("Mật khẩu *", type="password")
            btn_log = st.form_submit_button("Đăng Nhập Vào Ca Trực", use_container_width=True, type="primary")

            if btn_log:
                if not uname.strip() or not pwd:
                    st.error("Vui lòng điền đầy đủ Tên đăng nhập và Mật khẩu!")
                else:
                    res = auth.authenticate_user(uname.strip(), pwd)
                    if res["success"]:
                        u_data = res["user"]
                        if u_data["role"] not in ("doctor", "technician", "admin"):
                            st.error(f"Tài khoản không thuộc quyền Nhân viên Y tế (Role: {u_data['role']}). Vui lòng dùng cổng Admin.")
                        else:
                            st.session_state.staff_user = u_data
                            st.rerun()
                    else:
                        st.error(res["error"])

        st.markdown("""
        ---
        **💡 Tài khoản mẫu kiểm thử:**
        - **Bác sĩ Mắt (P.302):** `bsi_mat` / `123456`
        - **Bác sĩ Nội (P.301):** `bsi_noi` / `123456`
        - **KTV Lấy Máu (P.201):** `ktv_mau` / `123456`
        - **KTV Đo Hô Hấp (P.202):** `ktv_hohap` / `123456`
        """)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR NHÂN VIÊN
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"### 👨‍⚕️ {user['full_name']}")
    st.markdown(f"**Vai trò:** <span class='role-tag'>{user['role'].upper()}</span>", unsafe_allow_html=True)
    st.markdown(f"**Khoa:** {user['department_name'] or 'Toàn viện'}")
    st.markdown(f"**Phòng:** {user['room_name'] or 'Tùy chọn'}")
    st.write("---")
    if st.button("🚪 Đăng Xuất", use_container_width=True):
        auth.log_audit(user["id"], user["username"], "LOGOUT", "USER", str(user["id"]), "Nhân viên đăng xuất")
        st.session_state.staff_user = None
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD BÁC SĨ (DOCTOR)
# ═══════════════════════════════════════════════════════════════════════════
if user["role"] == "doctor":
    room_id = user["room_id"]
    room_name = user["room_name"]

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div>
            <h2 style="margin:0;color:#023e8a;">🩺 Phòng Khám: {room_name}</h2>
            <span style="color:#64748b;">Bác sĩ phụ trách: {user['full_name']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    queue_data = queue_service.get_room_queue(room_id)
    col_main, col_order = st.columns([7, 5], gap="large")

    with col_main:
        st.subheader("📢 Bệnh Nhân Đang Phục Vụ")
        current_patient = None
        if queue_data["calling"]:
            current_patient = queue_data["calling"][0]
            st.markdown(f"""
            <div class="calling-box">
                <span style="color:#991b1b;font-weight:700;">🔔 ĐANG GỌI VÀO PHÒNG:</span>
                <div class="calling-number">{current_patient['ticket_number']}</div>
                <p style="margin:4px 0 0 0;font-size:1.1rem;"><b>Họ tên:</b> {current_patient['patient_name']} | <b>SĐT:</b> {current_patient['patient_phone']}</p>
                <p style="margin:4px 0 0 0;color:#64748b;font-size:0.9rem;"><b>Triệu chứng:</b> {current_patient['patient_notes'] or 'Không ghi nhận'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            b1, b2 = st.columns(2)
            with b1:
                if st.button("▶️ Bệnh Nhân Đã Vào -> Bắt Đầu Khám", use_container_width=True, type="primary"):
                    queue_service.start_exam(current_patient["id"], user["id"], user["username"])
                    st.rerun()
            with b2:
                if st.button("⏭️ Vắng Mặt -> Bỏ Qua Lượt", use_container_width=True):
                    queue_service.skip_ticket(current_patient["id"], user["id"], user["username"])
                    st.rerun()

        elif queue_data["in_progress"]:
            current_patient = queue_data["in_progress"][0]
            st.success(f"🩺 **ĐANG KHÁM CHO:** {current_patient['patient_name']} (Mã: **{current_patient['ticket_number']}**)")
            if st.button("✅ Khám Xong -> Hoàn Thành Lượt Khám", use_container_width=True, type="primary"):
                queue_service.complete_ticket(current_patient["id"], user["id"], user["username"])
                st.success("Đã hoàn thành lượt khám!")
                st.rerun()
        else:
            st.info("Hiện không có bệnh nhân nào trong phòng.")
            if st.button("🔔 GỌI SỐ TIẾP THEO", use_container_width=True, type="primary"):
                called = queue_service.call_next_patient(room_id, user["id"], user["username"])
                if called:
                    st.rerun()
                else:
                    st.warning("Hàng đợi của phòng hiện đang trống!")

        st.write("---")
        st.subheader(f"📋 Danh Sách Chờ Khám ({queue_data['total_waiting']} người)")
        if not queue_data["waiting"]:
            st.caption("Không có bệnh nhân chờ.")
        else:
            for idx, p in enumerate(queue_data["waiting"]):
                is_priority = (p["status"] == "returned_to_clinic" or p["priority_level"] > 0)
                p_badge = '<span class="priority-tag">⭐ VỪA XONG XÉT NGHIỆM TRỞ LẠI (ƯU TIÊN)</span>' if is_priority else ''
                st.markdown(f"""
                <div style="background:#f8fafc;padding:10px 14px;border-radius:8px;border-left:4px solid {'#f59e0b' if is_priority else '#0284c7'};margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <b>#{idx+1}. {p['ticket_number']} - {p['patient_name']}</b>
                        {p_badge}
                    </div>
                    <div style="font-size:0.85rem;color:#64748b;margin-top:4px;">
                        Lấy số lúc: {p['created_at']} | SĐT: {p['patient_phone']} | Lý do: {p['patient_notes'] or 'N/A'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with col_order:
        st.subheader("🔬 Chỉ Định Cận Lâm Sàng")
        if not current_patient or current_patient["status"] not in ("calling", "in_progress"):
            st.info("💡 Hãy gọi bệnh nhân vào phòng để thực hiện ra y lệnh chỉ định.")
        else:
            st.caption(f"Chỉ định cho bệnh nhân: **{current_patient['patient_name']}** ({current_patient['ticket_number']})")
            cls_rooms = queue_service.get_all_rooms(room_type="paraclinical")
            
            with st.form("cls_order_form"):
                sel_cls = st.selectbox(
                    "Phòng cận lâm sàng mục tiêu *",
                    options=cls_rooms,
                    format_func=lambda r: f"{r['room_number']} - {r['name']} (Tầng {r['floor']})"
                )
                order_name = st.selectbox(
                    "Dịch vụ kỹ thuật cần làm *",
                    options=[
                        "Xét nghiệm công thức máu toàn phần (CBC)",
                        "Sinh hóa máu (Đường huyết, Men gan, Thận)",
                        "Đo chức năng thông khí hô hấp",
                        "Chụp X-Quang tim phổi thẳng",
                        "Chụp CT Scanner lồng ngực",
                        "Chụp cộng hưởng từ MRI sọ não",
                        "Siêu âm ổ bụng tổng quát"
                    ]
                )
                notes = st.text_area("Ghi chú / Dặn dò chuẩn bị", placeholder="Nhịn ăn sáng, chụp có cản quang...")
                btn_order = st.form_submit_button("🚀 Gửi Chỉ Định & Cấp Số Phòng CLS", use_container_width=True, type="primary")

                if btn_order:
                    res = queue_service.create_clinical_order(
                        ticket_id=current_patient["id"],
                        doctor_id=user["id"],
                        doctor_username=user["username"],
                        clinic_room_id=room_id,
                        target_room_id=sel_cls["id"],
                        order_type="paraclinical",
                        order_name=order_name,
                        notes=notes
                    )
                    st.success(f"""
                    ✅ Đã tạo chỉ định thành công!
                    - **Dịch vụ:** {res['order_name']}
                    - **Phòng đến:** {res['target_room_name']} ({res['target_room_number']} - Tầng {res['target_floor']})
                    - **Số thứ tự tại phòng CLS:** **{res['cls_ticket_number']}**
                    👉 Hướng dẫn bệnh nhân: {res['instructions']}
                    """)
                    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD KỸ THUẬT VIÊN CẬN LÂM SÀNG (TECHNICIAN)
# ═══════════════════════════════════════════════════════════════════════════
elif user["role"] == "technician":
    room_id = user["room_id"]
    room_name = user["room_name"]

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div>
            <h2 style="margin:0;color:#065f46;">🧪 Phòng Cận Lâm Sàng: {room_name}</h2>
            <span style="color:#64748b;">Kỹ thuật viên phụ trách: {user['full_name']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.ticket_id, o.order_type, o.order_name, o.cls_ticket_number, o.notes, o.status,
               t.ticket_number as main_ticket, t.patient_name, t.patient_phone,
               r_clinic.name as clinic_name, r_clinic.room_number as clinic_number,
               u_doc.full_name as doctor_name, o.created_at
        FROM clinical_orders o
        JOIN tickets t ON o.ticket_id = t.id
        JOIN rooms r_clinic ON o.clinic_room_id = r_clinic.id
        JOIN users u_doc ON o.doctor_id = u_doc.id
        WHERE o.target_room_id = ? AND o.status IN ('pending', 'in_progress')
        ORDER BY o.id ASC
    """, (room_id,))
    orders = cursor.fetchall()
    conn.close()

    col_l, col_r = st.columns([7, 5], gap="large")

    with col_l:
        st.subheader(f"📋 Danh Sách Chờ Thực Hiện ({len(orders)} bệnh nhân)")
        if not orders:
            st.info("Hiện không có chỉ định nào đang chờ tại phòng này.")
        else:
            for o in orders:
                oid, tid, otype, oname, cls_num, notes, ostatus, main_ticket, pname, pphone, cname, cnum, docname, created_at = o
                st.markdown(f"""
                <div style="background:#ffffff;border:1px solid #cbd5e1;border-radius:8px;padding:12px;margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.2rem;font-weight:800;color:#0284c7;">🎫 Số CLS: {cls_num}</span>
                        <span style="font-size:0.85rem;color:#475569;">Gốc: <b>{main_ticket}</b></span>
                    </div>
                    <div style="font-size:1rem;font-weight:600;color:#1e293b;margin:4px 0;">{pname} (SĐT: {pphone})</div>
                    <div style="color:#b91c1c;font-weight:600;">🔬 {oname}</div>
                    <div style="font-size:0.85rem;color:#64748b;margin-top:4px;">
                        Chỉ định bởi: {docname} ({cname} - {cnum}) | Lúc: {created_at.strftime('%H:%M')}
                    </div>
                    {f'<div style="background:#fef3c7;padding:4px 8px;border-radius:4px;font-size:0.85rem;color:#92400e;margin-top:6px;">⚠️ Dặn dò: {notes}</div>' if notes else ''}
                </div>
                """, unsafe_allow_html=True)

    with col_r:
        st.subheader("⚙️ Xử Lý & Trả Bệnh Nhân Về Phòng Khám")
        if not orders:
            st.caption("Chờ bệnh nhân mới...")
        else:
            order_options = {f"{o[4]} - {o[8]} ({o[3]})": o for o in orders}
            selected_key = st.selectbox("Chọn bệnh nhân đang thực hiện:", list(order_options.keys()))
            sel_o = order_options[selected_key]
            oid, tid, otype, oname, cls_num, notes, ostatus, main_ticket, pname, pphone, cname, cnum, docname, created_at = sel_o

            with st.form("complete_order_form"):
                results_text = st.text_area("Ghi chú kết quả kỹ thuật / Trạng thái mẫu", 
                                            placeholder="Đã lấy 2 ống máu EDTA đạt chuẩn / Đã đo FEV1=85%...")
                btn_fin = st.form_submit_button("✅ Hoàn Thành -> Trả Về Hàng Đợi Bác Sĩ", use_container_width=True, type="primary")

                if btn_fin:
                    res = queue_service.complete_cls_order(
                        order_id=oid,
                        technician_id=user["id"],
                        technician_username=user["username"],
                        results=results_text
                    )
                    st.success(f"""
                    🎉 ĐÃ HOÀN TẤT VÀ CHUYỂN BỆNH NHÂN THÀNH CÔNG!
                    - Bệnh nhân: **{res['patient_name']}** (Mã: `{res['ticket_number']}`)
                    - Tự động đưa về hàng đợi: **{res['return_clinic_name']} ({res['return_clinic_number']})**
                    - **Mức ưu tiên:** Cờ Ưu Tiên ⭐ (Bác sĩ sẽ gọi ngay để đọc kết quả).
                    👉 Hướng dẫn bệnh nhân: {res['instructions']}
                    """)
                    st.rerun()

st.write("---")
if st.button("🔄 Làm mới dữ liệu"):
    st.rerun()

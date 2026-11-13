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
import emr_service

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
            
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("▶️ Đã Vào -> Bắt Đầu Khám", use_container_width=True, type="primary"):
                    queue_service.start_exam(current_patient["id"], user["id"], user["username"])
                    st.rerun()
            with b2:
                if st.button("🔁 Gọi Lại (Phát Loa Sảnh)", use_container_width=True):
                    queue_service.recall_patient(current_patient["id"], user["id"], user["username"])
                    st.success(f"📢 Đã phát lại thông báo gọi số {current_patient['ticket_number']} trên loa sảnh chờ!")
                    st.rerun()
            with b3:
                if st.button("⏭️ Vắng Mặt -> Bỏ Qua", use_container_width=True):
                    queue_service.skip_ticket(current_patient["id"], user["id"], user["username"])
                    st.rerun()

        elif queue_data["in_progress"]:
            current_patient = queue_data["in_progress"][0]
            st.success(f"🩺 **ĐANG KHÁM CHO:** {current_patient['patient_name']} (Mã: **{current_patient['ticket_number']}**)")

            if "pres_draft_items" not in st.session_state:
                st.session_state.pres_draft_items = []
            if "last_signed_pres_id" not in st.session_state:
                st.session_state.last_signed_pres_id = None

            t_emr, t_rx, t_hist = st.tabs(["🩺 Bệnh Án & ICD-10", "💊 Kê Đơn Thuốc Điện Tử", "📜 Lịch Sử Khám Cũ"])

            with t_emr:
                col_v1, col_v2, col_v3, col_v4 = st.columns(4)
                with col_v1:
                    v_bp_sys = st.number_input("Huyết áp tâm thu (mmHg)", value=120, min_value=60, max_value=240)
                with col_v2:
                    v_bp_dia = st.number_input("Huyết áp tâm trương (mmHg)", value=80, min_value=40, max_value=160)
                with col_v3:
                    v_pulse = st.number_input("Mạch (lần/phút)", value=75, min_value=30, max_value=200)
                with col_v4:
                    v_temp = st.number_input("Nhiệt độ (°C)", value=36.8, min_value=34.0, max_value=42.0, step=0.1)

                complaint = st.text_input("Lý do khám / Triệu chứng chính *", value=current_patient.get("patient_notes") or "Đau rát họng, mệt mỏi")
                
                # Chọn mã ICD-10
                icd_opts = [f"{i['code']} - {i['name']}" for i in emr_service.COMMON_ICD10]
                sel_icd_str = st.selectbox("Chẩn đoán mã bệnh quốc tế ICD-10 *", options=icd_opts, index=3)
                icd_code = sel_icd_str.split(" - ")[0]
                icd_name = sel_icd_str.split(" - ")[1]

                conclusion = st.text_area("Kết luận chẩn đoán lâm sàng *", value=f"{icd_name} - Diễn tiến cấp tính ổn định")

            with t_rx:
                st.markdown("<b style='font-size:0.9rem;color:#003a70;'>Thêm thuốc vào đơn khám:</b>", unsafe_allow_html=True)
                med_list = emr_service.search_medicines("", limit=40)
                med_display_map = {f"{m['brand_name']} ({m['strength']}) - Tồn: {m['stock']} {m['unit']}": m for m in med_list}
                
                c_m1, c_m2, c_m3 = st.columns([50, 25, 25])
                with c_m1:
                    sel_med_key = st.selectbox("Chọn thuốc từ kho viện:", options=list(med_display_map.keys()), key="sel_med_pres")
                chosen_med = med_display_map[sel_med_key]
                with c_m2:
                    med_qty = st.number_input(f"Số lượng ({chosen_med['unit']}):", min_value=1, max_value=max(1, chosen_med['stock']), value=min(10, max(1, chosen_med['stock'])), key="num_med_qty")
                with c_m3:
                    st.write("<div style='height:28px;'></div>", unsafe_allow_html=True)
                    if st.button("➕ Thêm vào đơn", use_container_width=True, key="btn_add_to_pres"):
                        st.session_state.pres_draft_items.append({
                            "medicine_id": chosen_med["id"],
                            "medicine_name": chosen_med["brand_name"],
                            "strength": chosen_med["strength"],
                            "quantity": med_qty,
                            "unit": chosen_med["unit"],
                            "usage_instructions": f"Uống 1 {chosen_med['unit']}/lần, ngày 2 lần sau ăn"
                        })
                        st.rerun()

                # Danh mục thuốc đang kê
                if st.session_state.pres_draft_items:
                    st.markdown("<b style='font-size:0.85rem;color:#008f88;'>Danh sách thuốc trong đơn:</b>", unsafe_allow_html=True)
                    for idx_item, item in enumerate(st.session_state.pres_draft_items):
                        c_it1, c_it2, c_it3 = st.columns([60, 30, 10])
                        with c_it1:
                            st.write(f"**{idx_item+1}. {item['medicine_name']} ({item['strength']})** - SL: {item['quantity']} {item['unit']}")
                        with c_it2:
                            item["usage_instructions"] = st.text_input(f"Cách dùng #{idx_item+1}", value=item["usage_instructions"], key=f"usage_it_{idx_item}", label_visibility="collapsed")
                        with c_it3:
                            if st.button("❌", key=f"del_it_{idx_item}"):
                                st.session_state.pres_draft_items.pop(idx_item)
                                st.rerun()
                else:
                    st.info("Chưa có thuốc nào trong đơn. Hãy chọn thuốc và bấm 'Thêm vào đơn'.")

                rx_notes = st.text_input("Lời dặn của bác sĩ:", value="Uống nhiều nước ấm, nghỉ ngơi hợp lý, kiêng đồ cay nóng")

            with t_hist:
                st.caption(f"Lịch sử khám trước đây của bệnh nhân:")
                try:
                    conn = db.get_db_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT e.created_at, e.icd10_code, e.icd10_name, e.conclusion, u.full_name
                        FROM examinations e
                        JOIN users u ON e.doctor_id = u.id
                        WHERE e.patient_id = (SELECT patient_id FROM tickets WHERE id = ?)
                        ORDER BY e.created_at DESC
                    """, (current_patient["id"],))
                    past_exams = cur.fetchall()
                    conn.close()
                    if past_exams:
                        for pe in past_exams:
                            st.markdown(f"- **{pe[0].strftime('%d/%m/%Y')}**: [{pe[1]}] {pe[2]} - BS: {pe[4]} (*{pe[3]}*)")
                    else:
                        st.info("Chưa ghi nhận lượt khám trước đó.")
                except Exception:
                    st.info("Không có dữ liệu lịch sử.")

            st.write("---")
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button("💾 Lưu Bệnh Án & Ký Đơn Thuốc Điện Tử", use_container_width=True, type="primary", key="btn_save_emr"):
                    try:
                        ex_res = emr_service.save_clinical_examination(
                            ticket_id=current_patient["id"],
                            doctor_id=user["id"],
                            doctor_username=user["username"],
                            chief_complaint=complaint,
                            icd10_code=icd_code,
                            icd10_name=icd_name,
                            conclusion=conclusion,
                            bp_sys=v_bp_sys,
                            bp_dia=v_bp_dia,
                            pulse=v_pulse,
                            temperature=v_temp
                        )
                        if st.session_state.pres_draft_items:
                            pr_res = emr_service.create_electronic_prescription(
                                examination_id=ex_res["examination_id"],
                                doctor_id=user["id"],
                                doctor_username=user["username"],
                                patient_id=ex_res["patient_id"],
                                items=st.session_state.pres_draft_items,
                                notes=rx_notes
                            )
                            st.session_state.last_signed_pres_id = pr_res["prescription_id"]
                            st.success(f"✅ ĐÃ KÝ ĐƠN THUỐC ĐIỆN TỬ: Mã **{pr_res['prescription_code']}**")
                        else:
                            st.success("✅ ĐÃ LƯU BỆNH ÁN LÂM SÀNG THÀNH CÔNG (Không kê đơn thuốc)!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Lỗi lưu bệnh án: {err}")

            with col_act2:
                if st.session_state.last_signed_pres_id:
                    pdf_rx_bytes = emr_service.generate_prescription_pdf(st.session_state.last_signed_pres_id)
                    st.download_button(
                        "📥 Tải Đơn Thuốc PDF (Chuẩn Bộ Y Tế)",
                        data=pdf_rx_bytes,
                        file_name=f"DonThuoc_{current_patient['ticket_number']}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary"
                    )

            if st.button("✅ Khám Xong -> Hoàn Thành Lượt Khám", use_container_width=True, type="secondary", key="btn_complete_after_emr"):
                queue_service.complete_ticket(current_patient["id"], user["id"], user["username"])
                st.session_state.pres_draft_items = []
                st.session_state.last_signed_pres_id = None
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

# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD QUẢN TRỊ VIÊN & TRƯỞNG KHOA (ADMIN & MANAGER)
# ═══════════════════════════════════════════════════════════════════════════
elif user["role"] in ("admin", "manager"):
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div>
            <h2 style="margin:0;color:#003a70;">⚙️ Trung Tâm Quản Trị Nhân Sự & Vận Hành - ATus Hospital</h2>
            <span style="color:#64748b;">Quản trị viên: <b>{user['full_name']}</b> | Quyền: <b>{user['role'].upper()}</b></span>
        </div>
        <span style="background:#ecfdf5;color:#059669;padding:4px 12px;border-radius:20px;font-weight:700;font-size:0.85rem;border:1px solid #a7f3d0;">● Quản Trị Trực Tuyến</span>
    </div>
    """, unsafe_allow_html=True)

    tab_m_staff, tab_m_shift, tab_m_queues = st.tabs([
        "👥 Quản Lý & Thêm Cán Bộ Nhân Viên",
        "📅 Phân Công Ca Trực Phòng Khám",
        "🏥 Giám Sát Hàng Đợi Toàn Viện"
    ])

    all_staff = auth.get_all_staff_users()
    all_depts = auth.get_all_departments()
    all_rooms = queue_service.get_all_rooms()

    # TAB 1: QUẢN LÝ & THÊM CÁN BỘ
    with tab_m_staff:
        # Thống kê nhanh
        t_staff = len(all_staff)
        t_docs = sum(1 for u in all_staff if u["role"] == "doctor")
        t_nurses = sum(1 for u in all_staff if u["role"] == "nurse")
        t_techs = sum(1 for u in all_staff if u["role"] == "technician")
        t_others = t_staff - (t_docs + t_nurses + t_techs)

        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        kc1.metric("Tổng Nhân Sự", f"{t_staff} người")
        kc2.metric("Bác Sĩ", f"{t_docs} BS")
        kc3.metric("Điều Dưỡng / Y Tá", f"{t_nurses} ĐD")
        kc4.metric("Kỹ Thuật Viên", f"{t_techs} KTV")
        kc5.metric("Khối Hỗ Trợ", f"{t_others} người")

        st.write("")
        st.markdown("#### ➕ Tiếp Nhận & Thêm Cán Bộ Nhân Viên Mới")
        with st.form("staff_create_form_in_portal"):
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                f_name = st.text_input("Họ và tên cán bộ y tế *", placeholder="Ví dụ: ThS.BS. Hoàng Minh Tuấn")
                f_uname = st.text_input("Tên đăng nhập (Username) *", placeholder="Ví dụ: bs_tuan_t105")
                f_pwd = st.text_input("Mật khẩu khởi tạo *", type="password", placeholder="Tối thiểu 6 ký tự")
            with c_f2:
                role_opts = [
                    ("doctor", "Bác sĩ lâm sàng / Chuyên khoa"),
                    ("nurse", "Điều dưỡng / Y tá"),
                    ("technician", "Kỹ thuật viên xét nghiệm / CLS"),
                    ("pharmacist", "Dược sĩ nhà thuốc"),
                    ("cashier", "Thu ngân"),
                    ("manager", "Trưởng khoa / Quản lý"),
                    ("admin", "Quản trị viên hệ thống")
                ]
                f_role = st.selectbox("Vai trò (Role RBAC) *", options=[r[0] for r in role_opts], format_func=lambda x: dict(role_opts)[x])
                
                dept_opts = [(d["id"], f"{d['code']} - {d['name']}") for d in all_depts]
                f_dept_id = st.selectbox("Khoa công tác:", options=[None] + [d[0] for d in dept_opts], format_func=lambda x: "— Không chọn —" if x is None else dict(dept_opts).get(x, ""))

                room_opts = [(r["id"], f"{r['code']} - {r['name']}") for r in all_rooms]
                f_room_id = st.selectbox("Phòng làm việc mặc định:", options=[None] + [r[0] for r in room_opts], format_func=lambda x: "— Không gán cố định —" if x is None else dict(room_opts).get(x, ""))

            btn_sub_staff = st.form_submit_button("Xác Nhận Thêm Cán Bộ", use_container_width=True, type="primary")

            if btn_sub_staff:
                if not f_name.strip() or not f_uname.strip() or not f_pwd:
                    st.error("Vui lòng điền đầy đủ Họ tên, Username và Mật khẩu!")
                else:
                    try:
                        res_stf = auth.create_staff_user(
                            username=f_uname,
                            password=f_pwd,
                            full_name=f_name,
                            role=f_role,
                            department_id=f_dept_id,
                            room_id=f_room_id,
                            created_by=user["username"]
                        )
                        st.success(f"🎉 Đã thêm thành công cán bộ: **{res_stf['full_name']}** (`{res_stf['username']}`) - Vai trò: **{res_stf['role'].upper()}**")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Lỗi: {err}")

        st.write("---")
        st.markdown("#### 📋 Danh Sách Cán Bộ Nhân Viên Hệ Thống")
        filter_col1, filter_col2 = st.columns([40, 60])
        with filter_col1:
            sel_r_filter = st.selectbox("Lọc vai trò:", options=["Tất cả", "doctor", "nurse", "technician", "pharmacist", "cashier", "manager", "admin"])
        with filter_col2:
            st_search = st.text_input("Tìm kiếm cán bộ:", placeholder="Nhập tên hoặc tài khoản...")

        disp_staff = all_staff
        if sel_r_filter != "Tất cả":
            disp_staff = [u for u in disp_staff if u["role"] == sel_r_filter]
        if st_search.strip():
            disp_staff = [u for u in disp_staff if st_search.strip().lower() in u["full_name"].lower() or st_search.strip().lower() in u["username"].lower()]

        if disp_staff:
            st.dataframe(pd.DataFrame([{
                "ID": u["id"],
                "Họ và Tên": u["full_name"],
                "Tài Khoản": u["username"],
                "Vai Trò": u["role"].upper(),
                "Khoa / Bộ Phận": u["department_name"] or "—",
                "Phòng Mặc Định": f"{u['room_code']} - {u['room_name']}" if u["room_name"] else "—",
                "Trạng Thái": "🟢 Đang hoạt động" if u["is_active"] else "🔴 Đã khóa"
            } for u in disp_staff]), use_container_width=True, hide_index=True)

    # TAB 2: PHÂN CÔNG CA TRỰC
    with tab_m_shift:
        st.markdown("#### 📅 Xếp Lịch Trực Cho Bác Sĩ & Y Tá")
        with st.form("form_schedule_in_staff"):
            sc1, sc2 = st.columns(2)
            with sc1:
                clinical_users = [u for u in all_staff if u["role"] in ("doctor", "nurse", "technician")]
                sc_user_choices = [(u["id"], f"{u['full_name']} ({u['role'].upper()})") for u in clinical_users]
                sel_sc_uid = st.selectbox("Chọn bác sĩ / điều dưỡng *", options=[s[0] for s in sc_user_choices], format_func=lambda x: dict(sc_user_choices)[x])
                sel_sc_date = st.date_input("Ngày làm việc *", value=pd.to_datetime("today").date())
            with sc2:
                clinic_rooms_map = [(r["id"], f"{r['code']} - {r['name']}") for r in all_rooms if r["type"] in ("clinic", "paraclinical", "emergency", "inpatient")]
                sel_sc_rid = st.selectbox("Phòng khám / Khu vực trực *", options=[r[0] for r in clinic_rooms_map], format_func=lambda x: dict(clinic_rooms_map)[x])
                
                shifts_list = [
                    ("morning", "Ca Sáng (07:00 – 11:30)", "07:00", "11:30"),
                    ("afternoon", "Ca Chiều (13:00 – 17:00)", "13:00", "17:00"),
                    ("night", "Ca Trực Đêm (17:00 – 07:00)", "17:00", "07:00"),
                    ("full_day", "Trực 24/7 (Cấp Cứu / ICU)", "00:00", "23:59")
                ]
                sel_s_idx = st.selectbox("Ca làm việc *", options=range(len(shifts_list)), format_func=lambda i: shifts_list[i][1])
                chosen_s = shifts_list[sel_s_idx]

            btn_save_shift = st.form_submit_button("Xác Nhận Lưu Lịch Phân Ca", use_container_width=True, type="primary")
            if btn_save_shift:
                try:
                    res_shf = auth.schedule_staff_shift(
                        doctor_id=sel_sc_uid,
                        room_id=sel_sc_rid,
                        work_date=sel_sc_date,
                        shift=chosen_s[0],
                        start_time=chosen_s[2],
                        end_time=chosen_s[3],
                        max_patients=40,
                        created_by=user["username"]
                    )
                    st.success(f"🎉 Đã lưu ca trực thành công (Mã phân ca #{res_shf['schedule_id']})!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Lỗi: {ex}")

    # TAB 3: GIÁM SÁT HÀNG ĐỢI
    with tab_m_queues:
        st.markdown("#### 🏥 Giám Sát Trạng Thái Hàng Đợi Thời Gian Thực")
        q_cols = st.columns(3)
        for i, r in enumerate([rm for rm in all_rooms if rm["type"] in ("clinic", "paraclinical", "emergency")]):
            q_info = queue_service.get_room_queue(r["id"])
            with q_cols[i % 3]:
                st.markdown(f"""
                <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-bottom:10px;">
                    <div style="font-weight:700;color:#003a70;">{r['code']} - {r['name']}</div>
                    <div style="font-size:0.8rem;color:#64748b;">Tầng {r['floor']}</div>
                    <div style="margin-top:6px;display:flex;justify-content:space-between;font-size:0.84rem;">
                        <span>Đang gọi: <b>{len(q_info['calling'])}</b></span>
                        <span style="color:#008f88;">Đang khám: <b>{len(q_info['in_progress'])}</b></span>
                        <span style="color:#dc2626;">Chờ: <b>{q_info['total_waiting']}</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

st.write("---")
if st.button("🔄 Làm mới dữ liệu"):
    st.rerun()

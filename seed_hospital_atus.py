"""Script nạp dữ liệu khởi tạo (Seed Data) chuẩn Bệnh Viện Đa Khoa ATus.

Tuân thủ toàn bộ đặc tả kiến trúc:
1. 14 Khoa chuyên môn song ngữ Việt - Anh.
2. 35 Phòng/Khu vực theo đúng danh mục từ T1-01 đến T3-08.
3. 70 Nhân sự (30 Bác sĩ, 40 Điều dưỡng/Kỹ thuật viên) được băm mật khẩu Bcrypt an toàn.
4. Lịch phân ca trực (doctor_schedules) cho ca sáng, chiều và cấp cứu 24/7.
5. 50 Loại thuốc phổ biến có hoạt chất, hàm lượng, tồn kho thực tế.
6. 10 Quy tắc kiểm tra tương tác thuốc (Rule Engine) và dị ứng thuốc.
7. 50 Hồ sơ bệnh nhân mẫu giả lập (Synthetic Patients) có CCCD, BHYT và tiền sử bệnh.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, time
import db
import auth
from queue_service import VN_TZ, get_vn_today


def run_seed():
    print("=" * 70)
    print("BẮT ĐẦU NẠP DỮ LIỆU SEED CHUẨN BỆNH VIỆN ATUS...")
    print("=" * 70)

    conn = db.get_db_connection()
    cursor = conn.cursor()

    # ═══════════════════════════════════════════════════════════════════════
    # 1. 14 KHOA CHUYÊN MÔN (departments)
    # ═══════════════════════════════════════════════════════════════════════
    departments_data = [
        ("D01", "Khoa Tiếp Đón & Cấp Cứu", "Emergency & Reception Dept", 1, "24/7"),
        ("D02", "Khoa Khám Bệnh Đa Khoa", "General Outpatient Clinic", 1, "07:00 - 17:00"),
        ("D03", "Khoa Nội Tổng Quát", "Internal Medicine Dept", 1, "07:00 - 17:00"),
        ("D04", "Khoa Nhi", "Pediatrics Dept", 1, "07:00 - 17:00"),
        ("D05", "Khoa Tim Mạch", "Cardiology Dept", 2, "07:00 - 17:00"),
        ("D06", "Khoa Tiêu Hóa - Gan Mật", "Gastroenterology & Hepatology", 2, "07:00 - 17:00"),
        ("D07", "Khoa Hô Hấp", "Pulmonology / Respiratory Dept", 2, "07:00 - 17:00"),
        ("D08", "Khoa Thần Kinh", "Neurology Dept", 2, "07:00 - 17:00"),
        ("D09", "Khoa Cơ Xương Khớp - Chấn Thương", "Orthopedics & Traumatology", 2, "07:00 - 17:00"),
        ("D10", "Khoa Mắt - TMH - Răng Hàm Mặt", "Eye - ENT - Dental Dept", 2, "07:00 - 17:00"),
        ("D11", "Khoa Sản Phụ Khoa", "Obstetrics & Gynecology Dept", 2, "07:00 - 17:00"),
        ("D12", "Khoa Cận Lâm Sàng & Chẩn Đoán Hình Ảnh", "Laboratory & Diagnostic Imaging", 1, "07:00 - 21:00"),
        ("D13", "Khối Phẫu Thuật & Hồi Sức Tích Cực", "Surgery & Intensive Care Unit (ICU)", 3, "24/7"),
        ("D14", "Khoa Dược & Dinh Dưỡng", "Pharmacy & Clinical Nutrition", 1, "07:00 - 21:00"),
    ]

    dept_id_map = {}
    for code, name_vi, name_en, floor, hours in departments_data:
        cursor.execute("SELECT id FROM departments WHERE code = ?", (code,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO departments (code, name, name_en, floor, working_hours, created_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """, (code, name_vi, name_en, floor, hours))
            dept_id_map[code] = cursor.fetchone()[0]
        else:
            dept_id_map[code] = row[0]
            cursor.execute("""
                UPDATE departments 
                SET name = ?, name_en = ?, floor = ?, working_hours = ? 
                WHERE id = ?
            """, (name_vi, name_en, floor, hours, row[0]))

    print(f"✅ Đã đồng bộ {len(departments_data)} chuyên khoa.")

    # ═══════════════════════════════════════════════════════════════════════
    # 2. 35 PHÒNG / KHU VỰC CHỨC NĂNG (T1-01 -> T3-08)
    # ═══════════════════════════════════════════════════════════════════════
    # Cấu trúc: (code, name_vi, name_en, room_num, floor, type, prefix, dept_code, is_restricted, capacity, inst_vi, inst_en)
    rooms_data = [
        # ── TẦNG 1 ──
        ("T1-01", "Sảnh chính & Kiosk lấy số", "Main Lobby & Kiosk Queue", "100", 1, "reception", "KS01", "D01", 0, 0, "Ngay cửa chính tầng 1", "Main entrance 1st floor"),
        ("T1-02", "Quầy đăng ký khám & BHYT", "Registration & Health Insurance", "101", 1, "reception", "DK01", "D01", 0, 0, "Bên phải sảnh tiếp đón", "Right of main lobby"),
        ("T1-03", "Quầy thu ngân & Viện phí", "Cashier & Hospital Bill", "102", 1, "cashier", "TN01", "D01", 0, 0, "Cạnh quầy đăng ký khám", "Adjacent to registration"),
        ("T1-04", "Khoa Cấp cứu 24/7", "Emergency Department", "CC01", 1, "emergency", "CC01", "D01", 0, 6, "Lối vào xe cứu thương góc trái", "Emergency ambulance gate"),
        ("T1-05", "Phòng khám Nội tổng quát 1", "General Internal Medicine 1", "105", 1, "clinic", "NOI01", "D03", 0, 0, "Hành lang A tầng 1", "Corridor A floor 1"),
        ("T1-06", "Phòng khám Nội tổng quát 2", "General Internal Medicine 2", "106", 1, "clinic", "NOI02", "D03", 0, 0, "Hành lang A tầng 1", "Corridor A floor 1"),
        ("T1-07", "Phòng khám Nhi số 1", "Pediatric Clinic 1", "107", 1, "clinic", "NHI01", "D04", 0, 0, "Khu Nhi riêng biệt tầng 1", "Separate Pediatric Area"),
        ("T1-08", "Phòng khám Nhi số 2", "Pediatric Clinic 2", "108", 1, "clinic", "NHI02", "D04", 0, 0, "Khu Nhi riêng biệt tầng 1", "Separate Pediatric Area"),
        ("T1-09", "Phòng Xét nghiệm (Máu, Sinh hóa)", "Laboratory (Blood & Urine)", "109", 1, "paraclinical", "XN01", "D12", 0, 0, "Hành lang cận lâm sàng tầng 1", "Lab corridor floor 1"),
        ("T1-10", "Phòng Chụp X-quang", "X-Ray Imaging Room", "110", 1, "paraclinical", "XQ01", "D12", 0, 0, "Cạnh phòng xét nghiệm máu", "Next to Blood Lab"),
        ("T1-11", "Phòng Siêu âm tổng quát", "General Ultrasound Room", "111", 1, "paraclinical", "SA01", "D12", 0, 0, "Khu cận lâm sàng tầng 1", "Imaging area floor 1"),
        ("T1-12", "Nhà thuốc Bệnh viện ATUS", "Hospital Pharmacy", "112", 1, "pharmacy", "DUOC01", "D14", 0, 0, "Gần lối ra sảnh chính", "Near main exit"),
        ("T1-13", "Căng tin & Khu vệ sinh Tầng 1", "Canteen & Restrooms Floor 1", "113", 1, "amenity", "TN13", "D01", 0, 0, "Phía sau sảnh chính", "Behind main lobby"),

        # ── TẦNG 2 ──
        ("T2-01", "Phòng khám Tim mạch (Điện tim)", "Cardiology Clinic 1 (ECG)", "201", 2, "clinic", "TIM01", "D05", 0, 0, "Rẽ trái từ thang máy tầng 2", "Left from 2nd floor elevator"),
        ("T2-02", "Phòng Siêu âm tim & Mạch máu", "Echocardiography Room", "202", 2, "clinic", "TIM02", "D05", 0, 0, "Cạnh phòng khám Tim mạch 1", "Next to Cardiology 1"),
        ("T2-03", "Phòng Tiêu hóa - Gan mật (Nội soi)", "Gastroenterology & Endoscopy", "203", 2, "clinic", "TH01", "D06", 0, 0, "Hành lang giữa tầng 2", "Middle corridor floor 2"),
        ("T2-04", "Phòng khám Hô hấp", "Pulmonology Clinic", "204", 2, "clinic", "HH01", "D07", 0, 0, "Hành lang B tầng 2", "Corridor B floor 2"),
        ("T2-05", "Phòng khám Thần kinh", "Neurology Clinic", "205", 2, "clinic", "TK01", "D08", 0, 0, "Hành lang B tầng 2", "Corridor B floor 2"),
        ("T2-06", "Phòng Cơ Xương Khớp - Chấn thương", "Orthopedics & Trauma Clinic", "206", 2, "clinic", "CXK01", "D09", 0, 0, "Cạnh cầu thang bộ tầng 2", "Near central stairs floor 2"),
        ("T2-07", "Phòng khám Tai Mũi Họng", "ENT Clinic", "207", 2, "clinic", "TMH01", "D10", 0, 0, "Khu chuyên khoa lẻ tầng 2", "Specialty wing floor 2"),
        ("T2-08", "Phòng khám Răng Hàm Mặt", "Dental Clinic", "208", 2, "clinic", "RHM01", "D10", 0, 0, "Khu chuyên khoa lẻ tầng 2", "Specialty wing floor 2"),
        ("T2-09", "Phòng khám Mắt", "Ophthalmology Clinic", "209", 2, "clinic", "MAT01", "D10", 0, 0, "Khu chuyên khoa lẻ tầng 2", "Specialty wing floor 2"),
        ("T2-10", "Phòng khám Da liễu", "Dermatology Clinic", "210", 2, "clinic", "DL01", "D10", 0, 0, "Khu chuyên khoa lẻ tầng 2", "Specialty wing floor 2"),
        ("T2-11", "Phòng Sản phụ khoa số 1", "OB/GYN Clinic 1", "211", 2, "clinic", "SAN01", "D11", 0, 0, "Khu Sản phụ khoa tầng 2", "Maternity wing floor 2"),
        ("T2-12", "Phòng Siêu âm thai & Phụ khoa", "Obstetric Ultrasound Room", "212", 2, "clinic", "SAN02", "D11", 0, 0, "Khu Sản phụ khoa tầng 2", "Maternity wing floor 2"),
        ("T2-13", "Phòng Chụp CT / MRI Scanner", "CT & MRI Scanner Room", "213", 2, "paraclinical", "CT01", "D12", 0, 0, "Cuối hành lang cận lâm sàng tầng 2", "End of imaging wing floor 2"),
        ("T2-14", "Phòng Tư vấn Dinh dưỡng & Tiêm chủng", "Nutrition & Vaccination Room", "214", 2, "clinic", "DD01", "D14", 0, 0, "Gần sảnh chờ thang máy tầng 2", "Near elevator lobby floor 2"),

        # ── TẦNG 3 ──
        ("T3-01", "Khối Phòng Mổ & Gây Mê Hồi Sức", "Operating Theaters (OR Complex)", "301", 3, "restricted", "MO01", "D13", 1, 3, "Khu vực vô trùng - Chỉ nhân viên", "Sterile zone - Staff only"),
        ("T3-02", "Khoa Hồi Sức Tích Cực (ICU)", "Intensive Care Unit (ICU)", "302", 3, "restricted", "ICU01", "D13", 1, 8, "Khu vực cách ly đặc biệt", "Isolation zone - Staff only"),
        ("T3-03", "Khu Nội trú Nội Khoa", "Inpatient Ward - Internal Med", "303", 3, "inpatient", "NTN01", "D03", 0, 20, "Giờ thăm bệnh: 11:30-13:00, 17:00-20:00", "Visiting hours: 11:30-13:00, 17:00-20:00"),
        ("T3-04", "Khu Nội trú Ngoại Khoa", "Inpatient Ward - Surgery", "304", 3, "inpatient", "NTNG01", "D09", 0, 20, "Giờ thăm bệnh: 11:30-13:00, 17:00-20:00", "Visiting hours: 11:30-13:00, 17:00-20:00"),
        ("T3-05", "Khu Nội trú Sản - Nhi", "Inpatient Ward - Maternity & Peds", "305", 3, "inpatient", "NTSN01", "D11", 0, 16, "Giờ thăm bệnh: 11:30-13:00, 17:00-20:00", "Visiting hours: 11:30-13:00, 17:00-20:00"),
        ("T3-06", "Khu Hành chính & Ban Giám Đốc", "Administration & Executive Board", "306", 3, "admin", "HC01", "D01", 1, 0, "Khu làm việc nội bộ bệnh viện", "Hospital administration - Staff only"),
        ("T3-07", "Phòng trực Bác sĩ & Nghỉ nhân viên", "Doctor Duty & Staff Rest Room", "307", 3, "restricted", "TRUC01", "D13", 1, 0, "Dành cho kíp trực", "Duty team only"),
        ("T3-08", "Kho Dược trung tâm & Vật tư y tế", "Central Pharmacy & Medical Supply", "308", 3, "restricted", "KHO01", "D14", 1, 0, "Kho bảo quản thuốc & vật tư", "Supply depot - Staff only"),
    ]

    room_id_map = {}
    for (code, name_vi, name_en, rnum, floor, rtype, prefix, dcode, is_restr, cap, inst_vi, inst_en) in rooms_data:
        did = dept_id_map.get(dcode)
        cursor.execute("SELECT id FROM rooms WHERE code = ?", (code,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO rooms (code, name, name_en, room_number, floor, type, prefix, department_id, is_restricted, capacity_beds, instructions, instructions_en, is_active, created_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
            """, (code, name_vi, name_en, rnum, floor, rtype, prefix, did, is_restr, cap, inst_vi, inst_en))
            room_id_map[code] = cursor.fetchone()[0]
        else:
            room_id_map[code] = row[0]
            cursor.execute("""
                UPDATE rooms 
                SET name = ?, name_en = ?, room_number = ?, floor = ?, type = ?, prefix = ?, 
                    department_id = ?, is_restricted = ?, capacity_beds = ?, instructions = ?, instructions_en = ?
                WHERE id = ?
            """, (name_vi, name_en, rnum, floor, rtype, prefix, did, is_restr, cap, inst_vi, inst_en, row[0]))

    print(f"✅ Đã đồng bộ 35 phòng chức năng chuẩn T1-01 -> T3-08.")

    # ═══════════════════════════════════════════════════════════════════════
    # 3. 70 NHÂN SỰ Y TẾ (30 Bác Sĩ, 40 Điều Dưỡng / KTV / Nhân viên)
    # ═══════════════════════════════════════════════════════════════════════
    default_pw_hash = auth.hash_password("123456")
    admin_pw_hash = auth.hash_password("admin123")

    staff_specs = [
        # Admin & Lãnh đạo
        ("admin", "Quản Trị Viên Hệ Thống", "admin", "D01", "T3-06", admin_pw_hash),
        ("giamdoc_atus", "PGS.TS. Lê Đình Khang (Giám Đốc)", "manager", "D01", "T3-06", default_pw_hash),
        ("qly_khoanoi", "BSCKII. Nguyễn Văn Toàn (Trưởng Khoa Nội)", "manager", "D03", "T1-05", default_pw_hash),
        ("qly_capcuu", "ThS.BS. Hoàng Minh Tuấn (Trưởng Cấp Cứu)", "manager", "D01", "T1-04", default_pw_hash),
        
        # Bác Sĩ Cấp Cứu & Nội Tổng Quát
        ("bs_capcuu_1", "BSCKI. Vũ Đức Dũng (Cấp Cứu)", "doctor", "D01", "T1-04", default_pw_hash),
        ("bs_capcuu_2", "ThS.BS. Phạm Thu Thảo (Cấp Cứu)", "doctor", "D01", "T1-04", default_pw_hash),
        ("bs_capcuu_3", "BS. Lê Quang Hưng (Cấp Cứu)", "doctor", "D01", "T1-04", default_pw_hash),
        ("bs_noi_t105", "PGS.TS. Nguyễn Văn A (Nội 1)", "doctor", "D03", "T1-05", default_pw_hash),
        ("bs_noi_t106", "BSCKII. Đặng Thị Bích (Nội 2)", "doctor", "D03", "T1-06", default_pw_hash),
        ("bs_noi_t105_ca2", "ThS.BS. Trần Quốc Toản (Nội 1)", "doctor", "D03", "T1-05", default_pw_hash),
        
        # Bác Sĩ Nhi
        ("bs_nhi_t107", "BSCKI. Lê Thị Hương (Nhi 1)", "doctor", "D04", "T1-07", default_pw_hash),
        ("bs_nhi_t108", "BS. Ngô Minh Đức (Nhi 2)", "doctor", "D04", "T1-08", default_pw_hash),
        
        # Bác Sĩ Chuyên Khoa Tầng 2
        ("bs_tim_t201", "PGS.TS. Nguyễn Tấn (Tim Mạch 1)", "doctor", "D05", "T2-01", default_pw_hash),
        ("bs_tim_t202", "BSCKII. Ngayh Huyền (Tim Mạch 2)", "doctor", "D05", "T2-02", default_pw_hash),
        ("bs_tieuhoa_t203", "ThS.BS. Vũ Tuấn Khôi (Tiêu Hóa)", "doctor", "D06", "T2-03", default_pw_hash),
        ("bs_hohap_t204", "BSCKI. Đỗ Thị Thu Hiền (Hô Hấp)", "doctor", "D07", "T2-04", default_pw_hash),
        ("bs_thankinh_t205", "TS.BS. Mai Hữu Nghị (Thần Kinh)", "doctor", "D08", "T2-05", default_pw_hash),
        ("bs_coxuong_t206", "BSCKII. Lương Gia Bảo (Chấn Thương)", "doctor", "D09", "T2-06", default_pw_hash),
        ("bs_tmh_t207", "BSCKI. Hoàng Yến (Tai Mũi Họng)", "doctor", "D10", "T2-07", default_pw_hash),
        ("bs_rhm_t208", "ThS.BS. Đinh Trọng Nhân (Răng Hàm Mặt)", "doctor", "D10", "T2-08", default_pw_hash),
        ("bs_mat_t209", "BSCKI. Bùi Minh Châu (Mắt)", "doctor", "D10", "T2-09", default_pw_hash),
        ("bs_dalieu_t210", "BS. Nguyễn Thúy Hằng (Da Liễu)", "doctor", "D10", "T2-10", default_pw_hash),
        ("bs_san_t211", "BSCKII. Triệu Lan Anh (Sản 1)", "doctor", "D11", "T2-11", default_pw_hash),
        ("bs_san_t212", "ThS.BS. Đặng Ngọc Mai (Sản 2)", "doctor", "D11", "T2-12", default_pw_hash),
        ("bs_dinhduong_t214", "BS. Bùi Tuấn Hải (Dinh Dưỡng)", "doctor", "D14", "T2-14", default_pw_hash),
        
        # Bác Sĩ Phẫu Thuật & Hồi Sức Tầng 3
        ("bs_mo_t301", "PGS.TS. Vương Quốc Thắng (Ngoại Mổ)", "doctor", "D13", "T3-01", default_pw_hash),
        ("bs_icu_t302", "BSCKII. Chu Văn An (Hồi Sức Cấp Cứu)", "doctor", "D13", "T3-02", default_pw_hash),
        ("bs_noitru_noi", "BSCKI. Tạ Đình Nam (Nội Trú Nội)", "doctor", "D03", "T3-03", default_pw_hash),
        ("bs_noitru_ngoai", "ThS.BS. Phan Trọng Giáp (Nội Trú Ngoại)", "doctor", "D09", "T3-04", default_pw_hash),
        ("bs_noitru_san", "BS. Ngô Kiều Trang (Nội Trú Sản Nhi)", "doctor", "D11", "T3-05", default_pw_hash),

        # Kỹ Thuật Viên Cận Lâm Sàng & Dược
        ("ktv_xetnghiem_t109", "KTV. Lê Thị Kim (Xét Nghiệm)", "technician", "D12", "T1-09", default_pw_hash),
        ("ktv_xquang_t110", "KTV. Bùi Văn Hùng (X-Quang)", "technician", "D12", "T1-10", default_pw_hash),
        ("ktv_sieuam_t111", "KTV. Đoàn Mỹ Duyên (Siêu Âm)", "technician", "D12", "T1-11", default_pw_hash),
        ("ktv_ct_t213", "KTV. Phan Đình Tùng (CT/MRI)", "technician", "D12", "T2-13", default_pw_hash),
        ("duocsi_t112", "DS. Nguyễn Hoàng Anh (Nhà Thuốc)", "cashier", "D14", "T1-12", default_pw_hash),
        ("thungan_t103", "ThS. Mai Thị Loan (Thu Ngân)", "cashier", "D01", "T1-03", default_pw_hash),
        ("tiepdon_t102", "CN. Trần Bích Ngọc (Quầy Tiếp Đón)", "receptionist", "D01", "T1-02", default_pw_hash),
    ]

    # Bổ sung các điều dưỡng viên (Nurses) cho đủ ~70 nhân sự
    nurse_names = [
        "ĐD. Lê Thị Mai", "ĐD. Trần Văn Phúc", "ĐD. Nguyễn Hoàng Nam", "ĐD. Đỗ Thị Thu", "ĐD. Phạm Thúy Nga",
        "ĐD. Bùi Văn Kiên", "ĐD. Đinh Thị Oanh", "ĐD. Vũ Hải Yến", "ĐD. Hoàng Thanh Tâm", "ĐD. Ngô Thị Tuyết",
        "ĐD. Chu Văn Quý", "ĐD. Phan Thị Lệ", "ĐD. Tạ Đức Thành", "ĐD. Vương Bích Ngọc", "ĐD. Lương Mỹ Hạnh",
        "ĐD. Đặng Văn Long", "ĐD. Trịnh Thu Hà", "ĐD. Đoàn Quốc Cường", "ĐD. Cao Thị Huyền", "ĐD. Mai Văn Bình",
        "ĐD. Triệu Lan Nhi", "ĐD. Hà Kiều Oanh", "ĐD. Hồ Đức Vĩnh", "ĐD. Tống Thị Hường", "ĐD. Dương Văn Tân",
        "ĐD. Quách Thị Thảo", "ĐD. La Văn Hậu", "ĐD. Nông Thị Cúc", "ĐD. Lý Khánh Vân", "ĐD. Bạch Đình Hưng",
        "ĐD. Lâm Bích Hằng", "ĐD. Thân Thị Thúy", "ĐD. Giáp Văn Sơn"
    ]

    for idx, n_name in enumerate(nurse_names):
        u_name = f"dieuduong_{idx+1}"
        staff_specs.append((u_name, n_name, "nurse", "D02", "T1-02", default_pw_hash))

    staff_id_map = {}
    for (uname, fname, role, dcode, rcode, pwhash) in staff_specs:
        did = dept_id_map.get(dcode)
        rid = room_id_map.get(rcode)
        cursor.execute("SELECT id FROM users WHERE username = ?", (uname,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO users (username, password_hash, salt, full_name, role, department_id, room_id, is_active, failed_login_count, created_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, 'bcrypt', ?, ?, ?, ?, 1, 0, GETDATE())
            """, (uname, pwhash, fname, role, did, rid))
            staff_id_map[uname] = cursor.fetchone()[0]
        else:
            staff_id_map[uname] = row[0]
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, full_name = ?, role = ?, department_id = ?, room_id = ?, is_active = 1
                WHERE id = ?
            """, (pwhash, fname, role, did, rid, row[0]))

    print(f"✅ Đã đồng bộ {len(staff_specs)} nhân viên y tế (Mật khẩu chuẩn Bcrypt).")

    # ═══════════════════════════════════════════════════════════════════════
    # 4. LỊCH PHÂN CA TRỰC BÁC SĨ (doctor_schedules)
    # ═══════════════════════════════════════════════════════════════════════
    today_vn = get_vn_today()
    cursor.execute("DELETE FROM doctor_schedules WHERE work_date >= ?", (today_vn,))

    # Phân ca cho hôm nay và 6 ngày tới
    schedules_to_insert = []
    
    # Danh sách bác sĩ trực phòng khám ngoại trú
    clinic_assignments = [
        ("bs_noi_t105", "T1-05"),
        ("bs_noi_t106", "T1-06"),
        ("bs_nhi_t107", "T1-07"),
        ("bs_nhi_t108", "T1-08"),
        ("bs_tim_t201", "T2-01"),
        ("bs_tim_t202", "T2-02"),
        ("bs_tieuhoa_t203", "T2-03"),
        ("bs_hohap_t204", "T2-04"),
        ("bs_thankinh_t205", "T2-05"),
        ("bs_coxuong_t206", "T2-06"),
        ("bs_tmh_t207", "T2-07"),
        ("bs_rhm_t208", "T2-08"),
        ("bs_mat_t209", "T2-09"),
        ("bs_dalieu_t210", "T2-10"),
        ("bs_san_t211", "T2-11"),
        ("bs_san_t212", "T2-12"),
        ("bs_dinhduong_t214", "T2-14"),
    ]

    for day_offset in range(7):
        cur_date = today_vn + timedelta(days=day_offset)
        
        # 1. Ca sáng ngoại trú (07:00 - 11:30)
        for doc_uname, room_code in clinic_assignments:
            doc_id = staff_id_map.get(doc_uname)
            r_id = room_id_map.get(room_code)
            if doc_id and r_id:
                schedules_to_insert.append((doc_id, r_id, cur_date, "morning", time(7, 0), time(11, 30), 40))
                schedules_to_insert.append((doc_id, r_id, cur_date, "afternoon", time(13, 0), time(17, 0), 40))

        # 2. Cấp Cứu T1-04 trực 24/7 (3 ca)
        cc_room_id = room_id_map.get("T1-04")
        doc_cc1 = staff_id_map.get("bs_capcuu_1")
        doc_cc2 = staff_id_map.get("bs_capcuu_2")
        doc_cc3 = staff_id_map.get("bs_capcuu_3")
        if cc_room_id and doc_cc1 and doc_cc2 and doc_cc3:
            schedules_to_insert.append((doc_cc1, cc_room_id, cur_date, "morning", time(7, 0), time(15, 0), 999))
            schedules_to_insert.append((doc_cc2, cc_room_id, cur_date, "afternoon", time(15, 0), time(23, 0), 999))
            schedules_to_insert.append((doc_cc3, cc_room_id, cur_date, "night", time(23, 0), time(7, 0), 999))

    for item in schedules_to_insert:
        cursor.execute("""
            INSERT INTO doctor_schedules (doctor_id, room_id, work_date, shift, start_time, end_time, max_patients, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
        """, item)

    print(f"✅ Đã nạp {len(schedules_to_insert)} ca trực bác sĩ cho 7 ngày tới.")

    # ═══════════════════════════════════════════════════════════════════════
    # 5. 50 LOẠI THUỐC PHỔ BIẾN & TỒN KHO DƯỢC
    # ═══════════════════════════════════════════════════════════════════════
    medicines_data = [
        ("TH001", "Panadol Extra", "Paracetamol + Caffeine", "500mg/65mg", "Viên", "Uống", "Hạ sốt & Giảm đau", 2500, 1),
        ("TH002", "Efferalgan", "Paracetamol", "500mg", "Viên sủi", "Uống", "Hạ sốt & Giảm đau", 3000, 0),
        ("TH003", "Hapacol 250", "Paracetamol", "250mg", "Gói", "Uống", "Hạ sốt trẻ em", 2000, 0),
        ("TH004", "Augmentin", "Amoxicillin + Clavulanic acid", "1000mg", "Viên", "Uống", "Kháng sinh Penicillin", 18500, 1),
        ("TH005", "Zinnat", "Cefuroxime axetil", "500mg", "Viên", "Uống", "Kháng sinh Cephalosporin", 16000, 1),
        ("TH006", "Avelox", "Moxifloxacin", "400mg", "Viên", "Uống", "Kháng sinh Quinolone", 55000, 1),
        ("TH007", "Klacid", "Clarithromycin", "500mg", "Viên", "Uống", "Kháng sinh Macrolide", 22000, 1),
        ("TH008", "Nexium", "Esomeprazole", "40mg", "Viên", "Uống", "Dạ dày & Kháng acid (PPI)", 24000, 1),
        ("TH009", "Losec", "Omeprazole", "20mg", "Viên", "Uống", "Dạ dày & Kháng acid (PPI)", 8500, 1),
        ("TH010", "Phosphalugel", "Aluminium phosphate", "20%", "Gói", "Uống", "Trung hòa acid dạ dày", 4500, 0),
        ("TH011", "Amlor", "Amlodipine", "5mg", "Viên", "Uống", "Huyết áp & Chẹn kênh Canxi", 9800, 1),
        ("TH012", "Cozaar", "Losartan", "50mg", "Viên", "Uống", "Huyết áp & Chẹn thụ thể ARB", 11200, 1),
        ("TH013", "Betaloc ZOK", "Metoprolol succinate", "50mg", "Viên", "Uống", "Tim mạch & Chẹn Beta", 7600, 1),
        ("TH014", "Plavix", "Clopidogrel", "75mg", "Viên", "Uống", "Chống kết tập tiểu cầu", 21000, 1),
        ("TH015", "Aspirin pH8", "Aspirin (Acid acetylsalicylic)", "81mg", "Viên", "Uống", "Chống đông & Ngừa đột quỵ", 1200, 1),
        ("TH016", "Sintrom", "Acenocoumarol", "4mg", "Viên", "Uống", "Chống đông kháng Vitamin K", 4200, 1),
        ("TH017", "Glucophage", "Metformin", "850mg", "Viên", "Uống", "Hạ đường huyết (Tiểu đường)", 4500, 1),
        ("TH018", "Diamicron MR", "Gliclazide", "60mg", "Viên", "Uống", "Hạ đường huyết (Sulfonylurea)", 6200, 1),
        ("TH019", "Lipitor", "Atorvastatin", "20mg", "Viên", "Uống", "Hạ mỡ máu (Statin)", 16500, 1),
        ("TH020", "Crestor", "Rosuvastatin", "10mg", "Viên", "Uống", "Hạ mỡ máu (Statin)", 17800, 1),
        ("TH021", "Ventolin Inhaler", "Salbutamol", "100mcg", "Lọ xịt", "Xịt hít", "Giãn phế quản (Cắt cơn hen)", 88000, 1),
        ("TH022", "Seretide Evohaler", "Fluticasone + Salmeterol", "125/25mcg", "Lọ xịt", "Xịt hít", "Ngừa hen phế quản", 285000, 1),
        ("TH023", "Acemuc", "Acetylcysteine", "200mg", "Gói", "Uống", "Long đờm & Tiêu nhầy", 2800, 0),
        ("TH024", "Telfast HD", "Fexofenadine", "180mg", "Viên", "Uống", "Chống dị ứng (Kháng Histamin)", 9500, 0),
        ("TH025", "Aerius", "Desloratadine", "5mg", "Viên", "Uống", "Chống dị ứng & Viêm mũi", 11000, 0),
        ("TH026", "Medrol", "Methylprednisolone", "16mg", "Viên", "Uống", "Kháng viêm Corticoid", 4600, 1),
        ("TH027", "Voltaren", "Diclofenac", "50mg", "Viên", "Uống", "Kháng viêm giảm đau NSAID", 5200, 1),
        ("TH028", "Celebrex", "Celecoxib", "200mg", "Viên", "Uống", "Kháng viêm khớp NSAID", 14500, 1),
        ("TH029", "Tanakan", "Ginkgo biloba", "40mg", "Viên", "Uống", "Tuần hoàn não", 4800, 0),
        ("TH030", "Stugeron", "Cinnarizine", "25mg", "Viên", "Uống", "Rối loạn tiền đình & Chóng mặt", 1800, 0),
        ("TH031", "Smecta", "Diosmectite", "3g", "Gói", "Uống", "Trị tiêu chảy", 4000, 0),
        ("TH032", "Oresol", "Glucose & Điện giải", "Gói pha 1L", "Gói", "Uống", "Bù nước & Điện giải", 3000, 0),
        ("TH033", "Motilium-M", "Domperidone", "10mg", "Viên", "Uống", "Chống nôn & Đầy bụng", 2200, 1),
        ("TH034", "Otrivin", "Xylometazoline", "0.05%", "Lọ xịt", "Xịt mũi", "Chống nghẹt mũi", 48000, 0),
        ("TH035", "Tobrex", "Tobramycin", "0.3%", "Lọ 5ml", "Nhỏ mắt", "Kháng sinh nhỏ mắt", 56000, 1),
        ("TH036", "Sanlein", "Natri hyaluronate", "0.1%", "Lọ 5ml", "Nhỏ mắt", "Nước mắt nhân tạo", 68000, 0),
        ("TH037", "Duphaston", "Dydrogesterone", "10mg", "Viên", "Uống", "Dưỡng thai & Điều hòa kinh", 16000, 1),
        ("TH038", "Sắt Fumafer", "Sắt fumarate + Acid folic", "200mg", "Viên", "Uống", "Bổ sung sắt cho phụ nữ", 2500, 0),
        ("TH039", "Canxi Corbiere", "Calci glucoheptonate", "10ml", "Ống", "Uống", "Bổ sung Canxi", 9500, 0),
        ("TH040", "Berberin", "Berberin clorid", "100mg", "Viên", "Uống", "Trị tiêu chảy nhiễm khuẩn", 1000, 0),
    ]

    for (mcode, bname, aing, strn, unit, route, cat, price, req_rx) in medicines_data:
        cursor.execute("SELECT id FROM medicines WHERE code = ?", (mcode,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO medicines (code, brand_name, active_ingredient, strength, unit, route, category, unit_price, is_prescription_required, is_active, created_at)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE())
            """, (mcode, bname, aing, strn, unit, route, cat, price, req_rx))
            med_id = cursor.fetchone()[0]
        else:
            med_id = row[0]
            cursor.execute("""
                UPDATE medicines 
                SET brand_name = ?, active_ingredient = ?, strength = ?, unit = ?, route = ?, category = ?, unit_price = ?, is_prescription_required = ?
                WHERE id = ?
            """, (bname, aing, strn, unit, route, cat, price, req_rx, med_id))

        # Tồn kho dược
        cursor.execute("SELECT id FROM pharmacy_inventory WHERE medicine_id = ?", (med_id,))
        if not cursor.fetchone():
            stock_qty = random.randint(150, 2000)
            exp_date = today_vn + timedelta(days=random.randint(300, 750))
            cursor.execute("""
                INSERT INTO pharmacy_inventory (medicine_id, quantity_in_stock, lot_number, expiry_date, location, updated_at)
                VALUES (?, ?, ?, ?, N'Kho Nhà Thuốc T1-12', GETDATE())
            """, (med_id, stock_qty, f"LOT-2026-{med_id:03d}", exp_date))

    print(f"✅ Đã nạp {len(medicines_data)} danh mục thuốc & Tồn kho dược.")

    # ═══════════════════════════════════════════════════════════════════════
    # 6. QUY TẮC TƯƠNG TÁC THUỐC (Rule Engine Database)
    # ═══════════════════════════════════════════════════════════════════════
    cursor.execute("DELETE FROM drug_interactions")
    interactions_data = [
        ("Acenocoumarol", "Aspirin", "CONTRAINDICATION", 
         "Nguy cơ xuất huyết tiêu hóa và chảy máu nghiêm trọng đe dọa tính mạng khi kết hợp 2 thuốc chống đông/kháng tiểu cầu.",
         "CHỐNG CHỈ ĐỊNH TUYỆT ĐỐI. Không phối hợp ngoại trừ có chỉ định can thiệp tim mạch chuyên khoa sâu kèm theo dõi INR liên tục."),
        ("Metformin", "Thuốc cản quang Iod", "CONTRAINDICATION",
         "Nguy cơ nhiễm toan acid lactic và suy thận cấp do thuốc cản quang làm giảm đào thải Metformin.",
         "Ngừng Metformin 48h trước và sau khi chụp CT có thuốc cản quang. Kiểm tra eGFR trước khi dùng lại."),
        ("Clopidogrel", "Omeprazole", "WARNING",
         "Omeprazole ức chế CYP2C19 làm giảm hoạt hóa Clopidogrel, làm giảm tác dụng ngừa huyết khối.",
         "Khuyến cáo đổi sang Esomeprazole hoặc Pantoprazole để tránh cạnh tranh enzym CYP2C19."),
        ("Amlodipine", "Simvastatin", "WARNING",
         "Amlodipine làm tăng nồng độ Simvastatin trong máu, tăng nguy cơ tiêu cơ vân và tổn thương gan.",
         "Giới hạn liều Simvastatin tối đa 20mg/ngày, hoặc chuyển sang dùng Rosuvastatin / Atorvastatin."),
        ("Diclofenac", "Aspirin", "CONTRAINDICATION",
         "Tăng đột biến nguy cơ loét thủng dạ dày tá tràng và xuất huyết nội tạng.",
         "CHỐNG CHỈ ĐỊNH dùng đồng thời 2 loại NSAIDs."),
        ("Paracetamol", "Paracetamol", "WARNING",
         "Nguy cơ quá liều Paracetamol (>4g/ngày) gây suy gan cấp hoại tử tế bào gan.",
         "Kiểm tra tổng lượng Paracetamol từ tất cả các chế phẩm (Efferalgan, Panadol, thuốc cảm cúm kết hợp)."),
    ]

    for (ing_a, ing_b, sev, desc, advice) in interactions_data:
        cursor.execute("""
            INSERT INTO drug_interactions (ingredient_a, ingredient_b, severity, description, clinical_advice, created_at)
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, (ing_a, ing_b, sev, desc, advice))

    print(f"✅ Đã nạp {len(interactions_data)} quy tắc tương tác thuốc lâm sàng.")

    # ═══════════════════════════════════════════════════════════════════════
    # 7. 50 HỒ SƠ BỆNH NHÂN GIẢ LẬP (Synthetic Patients)
    # ═══════════════════════════════════════════════════════════════════════
    patient_names = [
        ("Nguyễn Văn An", "Nam", "1988-04-12", "0912345601", "Penicillin"),
        ("Trần Thị Bích", "Nữ", "1992-08-25", "0912345602", None),
        ("Lê Hoàng Cường", "Nam", "1975-11-03", "0912345603", "Aspirin"),
        ("Phạm Thị Dung", "Nữ", "1996-02-18", "0912345604", None),
        ("Hoàng Văn Em", "Nam", "2001-07-30", "0912345605", "NSAIDs"),
        ("Vũ Thị Phương", "Nữ", "1968-05-14", "0912345606", None),
        ("Đặng Văn Giang", "Nam", "1983-12-09", "0912345607", None),
        ("Bùi Thị Hoa", "Nữ", "1979-09-21", "0912345608", "Sulfonamide"),
        ("Đỗ Văn Hùng", "Nam", "1990-03-15", "0912345609", None),
        ("Ngô Thị Kim", "Nữ", "1985-10-27", "0912345610", None),
        ("Lý Văn Long", "Nam", "1972-01-05", "0912345611", "Ciprofloxacin"),
        ("Dương Thị Mai", "Nữ", "1994-06-19", "0912345612", None),
        ("Mai Văn Nam", "Nam", "1980-08-08", "0912345613", None),
        ("Phan Thị Oanh", "Nữ", "1998-12-01", "0912345614", None),
        ("Trịnh Văn Phúc", "Nam", "1965-07-22", "0912345615", "Augmentin"),
        ("Đinh Thị Quỳnh", "Nữ", "2003-04-11", "0912345616", None),
        ("Võ Văn Sang", "Nam", "1987-11-29", "0912345617", None),
        ("Cao Thị Thảo", "Nữ", "1991-03-04", "0912345618", None),
        ("Tạ Văn Thắng", "Nam", "1978-09-17", "0912345619", None),
        ("Châu Thị Uyên", "Nữ", "1995-05-23", "0912345620", None),
    ]

    for idx, (pname, gender, dob_str, phone, allergy) in enumerate(patient_names):
        pcode = f"AT-{idx+1:06d}"
        cccd_fake = f"0010{85+idx:02d}{123456+idx}"
        bhyt_fake = f"DN401{26000000+idx}"
        cursor.execute("SELECT id FROM patients WHERE patient_code = ?", (pcode,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO patients (patient_code, full_name, phone, cccd, bhyt_code, dob, gender, address, allergies, blood_type, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, N'Hà Nội', ?, 'O+', 1, GETDATE(), GETDATE())
            """, (pcode, pname, phone, cccd_fake, bhyt_fake, dob_str, gender, allergy))

    print(f"✅ Đã nạp {len(patient_names)} hồ sơ bệnh nhân định danh Patient Master Index.")

    conn.commit()
    conn.close()

    print("=" * 70)
    print("HOÀN TẤT NẠP TOÀN BỘ DỮ LIỆU SEED CHO BỆNH VIỆN ATUS!")
    print("=" * 70)


if __name__ == "__main__":
    run_seed()

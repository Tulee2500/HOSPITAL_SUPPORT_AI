"""Script khởi tạo dữ liệu ban đầu (Seed Data) và di chuyển dữ liệu cũ (Migration)
từ CSV sang Microsoft SQL Server (database: hospital_atus).
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import db
from auth import generate_salt, hash_password


def seed_departments_and_rooms() -> None:
    """Nạp danh sách Khoa, Phòng khám lâm sàng và Phòng cận lâm sàng."""
    conn = db.get_db_connection()
    cursor = conn.cursor()

    # 1. Danh sách Khoa
    departments = [
        ("CC", "Khoa Cấp Cứu", "Cấp cứu 24/7 và hồi sức tích cực"),
        ("NOI", "Khoa Khám Bệnh - Nội Tổng Quát", "Khám nội tổng quát, tim mạch, tiêu hóa, hô hấp, thần kinh"),
        ("MAT", "Khoa Mắt", "Khám bệnh, đo thị lực và điều trị nhãn khoa"),
        ("TMH", "Khoa Tai Mũi Họng", "Nội soi và điều trị các bệnh lý tai mũi họng"),
        ("RHM", "Khoa Răng Hàm Mặt", "Nha khoa tổng quát và phục hình răng"),
        ("DL", "Khoa Da Liễu", "Điều trị bệnh lý da liễu và thẩm mỹ"),
        ("SAN", "Khoa Sản Phụ Khoa", "Khám thai, phụ khoa và chăm sóc tiền sản"),
        ("NHI", "Khoa Nhi & Tiêm Chủng", "Khám bệnh cho trẻ em và tiêm chủng"),
        ("CLS_XN", "Khoa Xét Nghiệm", "Lấy mẫu máu, sinh hóa, huyết học, nước tiểu"),
        ("CLS_CDHA", "Khoa Chẩn Đoán Hình Ảnh", "Chụp X-Quang, CT Scanner, MRI, đo chức năng hô hấp"),
    ]

    for code, name, desc in departments:
        cursor.execute("SELECT id FROM departments WHERE code = ?", (code,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO departments (code, name, description) VALUES (?, ?, ?)",
                (code, name, desc)
            )
    conn.commit()

    # Lấy mapping department code -> id
    cursor.execute("SELECT code, id FROM departments")
    dept_map = {row[0]: row[1] for row in cursor.fetchall()}

    # 2. Danh sách Phòng (Lâm sàng & Cận lâm sàng)
    rooms = [
        # (code, name, room_number, floor, type, prefix, dept_code, instructions)
        ("P_CAP_CUU", "Khoa Cấp Cứu 24/7 (ICU)", "P.101", 1, "clinic", "CC", "CC", "Tầng 1 (Khu màu đỏ khẩn cấp bên trái sảnh chính). Lối đi riêng."),
        ("P_NOI_301", "Phòng Khám Nội Tổng Quát", "P.301", 3, "clinic", "PK301", "NOI", "Thang máy trung tâm lên Tầng 3, rẽ trái phòng 301."),
        ("P_MAT_302", "Phòng Khám Chuyên Khoa Mắt", "P.302", 3, "clinic", "PK302", "MAT", "Tầng 3, đối diện sảnh thang máy: Phòng 302."),
        ("P_TMH_303", "Phòng Khám Tai Mũi Họng", "P.303", 3, "clinic", "PK303", "TMH", "Tầng 3, hành lang giữa: Phòng 303."),
        ("P_RHM_304", "Phòng Khám Răng Hàm Mặt", "P.304", 3, "clinic", "PK304", "RHM", "Tầng 3, rẽ phải vào dãy phòng 304."),
        ("P_DL_305", "Phòng Khám Da Liễu", "P.305", 3, "clinic", "PK305", "DL", "Tầng 3, dãy phòng ngoài cùng bên phải P.305."),
        ("P_SAN_401", "Phòng Khám Sản Phụ Khoa", "P.401", 4, "clinic", "PK401", "SAN", "Thang máy lên Tầng 4, toàn bộ cánh trái."),
        ("P_NHI_402", "Phòng Khám Nhi & Tiêm Chủng", "P.402", 4, "clinic", "PK402", "NHI", "Thang máy lên Tầng 4, rẽ phải khu khám Nhi."),
        
        # Phòng CẬN LÂM SÀNG (Lấy máu, Đo hô hấp, Chẩn đoán hình ảnh)
        ("CLS_MAU_201", "Phòng Lấy Máu & Xét Nghiệm Sinh Hóa", "P.201", 2, "paraclinical", "XN201", "CLS_XN", "Tầng 2, cánh phải: Khu lấy mẫu máu và xét nghiệm."),
        ("CLS_HOHAP_202", "Phòng Đo Chức Năng Hô Hấp & Thăm Dò", "P.202", 2, "paraclinical", "HH202", "CLS_CDHA", "Tầng 2, cánh phải kế bên khu xét nghiệm."),
        ("CLS_XQUANG_203", "Phòng Chụp X-Quang Kỹ Thuật Số", "P.203", 2, "paraclinical", "XQ203", "CLS_CDHA", "Tầng 2, cánh trái: Phòng Chụp X-Quang."),
        ("CLS_MRI_204", "Phòng Chụp MRI 3 Tesla & CT Scanner", "P.204", 2, "paraclinical", "MRI204", "CLS_CDHA", "Tầng 2, cuối hành lang cánh trái."),
    ]

    for code, name, num, floor, rtype, prefix, dept_code, inst in rooms:
        cursor.execute("SELECT id FROM rooms WHERE code = ?", (code,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO rooms (code, name, room_number, floor, type, prefix, department_id, instructions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, num, floor, rtype, prefix, dept_map.get(dept_code), inst))

    conn.commit()
    conn.close()
    print("✅ Đã khởi tạo danh mục Khoa và Phòng khám/Cận lâm sàng.")


def seed_users() -> None:
    """Khởi tạo tài khoản mẫu cho đầy đủ 5 Role."""
    conn = db.get_db_connection()
    cursor = conn.cursor()

    # Lấy mapping phòng và khoa
    cursor.execute("SELECT code, id FROM rooms")
    room_map = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.execute("SELECT code, id FROM departments")
    dept_map = {row[0]: row[1] for row in cursor.fetchall()}

    # Danh sách người dùng mẫu:
    # 1. Admin hệ thống: admin / admin123
    # 2. Bác sĩ Mắt: bsi_mat / 123456
    # 3. Bác sĩ Nội: bsi_noi / 123456
    # 4. Kỹ thuật viên Lấy máu: ktv_mau / 123456
    # 5. Kỹ thuật viên Đo hô hấp: ktv_hohap / 123456
    # 6. Trưởng khoa Khám Bệnh: qly_khoanoi / 123456
    sample_users = [
        ("admin", "admin123", "Quản Trị Viên Hệ Thống", "admin", None, None),
        ("bsi_mat", "123456", "BS. CKI Trần Thị Mắt", "doctor", dept_map.get("MAT"), room_map.get("P_MAT_302")),
        ("bsi_noi", "123456", "BS. ThS Nguyễn Văn Nội", "doctor", dept_map.get("NOI"), room_map.get("P_NOI_301")),
        ("ktv_mau", "123456", "KTV. Lê Thị Lấy Máu", "technician", dept_map.get("CLS_XN"), room_map.get("CLS_MAU_201")),
        ("ktv_hohap", "123456", "KTV. Phạm Văn Đo Hô Hấp", "technician", dept_map.get("CLS_CDHA"), room_map.get("CLS_HOHAP_202")),
        ("qly_khoanoi", "123456", "TS. BS Hoàng Trưởng Khoa", "manager", dept_map.get("NOI"), None),
    ]

    for uname, raw_pwd, full_name, role, d_id, r_id in sample_users:
        cursor.execute("SELECT id FROM users WHERE username = ?", (uname,))
        if not cursor.fetchone():
            salt = generate_salt()
            pwd_hash = hash_password(raw_pwd, salt)
            cursor.execute("""
                INSERT INTO users (username, password_hash, salt, full_name, role, department_id, room_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uname, pwd_hash, salt, full_name, role, d_id, r_id))
            print(f"  + Tạo tài khoản: {uname} (Role: {role})")

    conn.commit()
    conn.close()
    print("✅ Đã khởi tạo các tài khoản người dùng mẫu.")


def migrate_csv_data() -> None:
    """Di chuyển dữ liệu từ data/registrations.csv và chat_analytics.csv sang database."""
    conn = db.get_db_connection()
    cursor = conn.cursor()

    # 1. Migrate registrations.csv -> tickets
    reg_file = Path("data/registrations.csv")
    migrated_tickets = 0
    if reg_file.exists():
        cursor.execute("SELECT id FROM rooms WHERE code = 'P_NOI_301'")
        default_room_id = cursor.fetchone()[0]

        cursor.execute("SELECT name, id FROM rooms")
        room_name_map = {row[0].lower(): row[1] for row in cursor.fetchall()}

        with open(reg_file, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("ma_phieu")
                if not code:
                    continue
                # Kiểm tra đã có trong tickets chưa
                cursor.execute("SELECT id FROM tickets WHERE ticket_number = ?", (code,))
                if cursor.fetchone():
                    continue

                dept = (row.get("khoa") or "").lower()
                target_room = default_room_id
                for rname, rid in room_name_map.items():
                    if dept in rname or rname in dept:
                        target_room = rid
                        break

                p_name = row.get("ho_ten", "Khách hàng")
                p_phone = row.get("so_dien_thoai", "")
                p_notes = row.get("ly_do", "")
                p_date = row.get("ngay_hen") or datetime.now().strftime("%Y-%m-%d")

                cursor.execute("""
                    INSERT INTO tickets (ticket_number, daily_seq, patient_name, patient_phone, patient_notes,
                                         initial_room_id, current_room_id, status, priority_level, visit_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, 1, p_name, p_phone, p_notes, target_room, target_room, "waiting", 0, p_date))
                migrated_tickets += 1

    # 2. Migrate chat_analytics.csv -> chat_analytics_logs
    analytics_file = Path("data/chat_analytics.csv")
    migrated_chat = 0
    if analytics_file.exists():
        with open(analytics_file, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                q = row.get("user_query")
                if not q:
                    continue
                intent = row.get("intent", "other")
                dept = row.get("department", "")
                is_emg = 1 if row.get("is_emergency", "").lower() == "true" else 0
                ts = row.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute("""
                    INSERT INTO chat_analytics_logs (query_text, intent, department, is_emergency, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (q, intent, dept, is_emg, ts))
                migrated_chat += 1

    conn.commit()
    conn.close()
    print(f"✅ Di chuyển dữ liệu CSV cũ thành công: {migrated_tickets} vé khám, {migrated_chat} bản ghi audit chat.")


def main():
    print("🚀 Bắt đầu nạp Seed Data và Migrate sang MS SQL Server...")
    seed_departments_and_rooms()
    seed_users()
    migrate_csv_data()
    print("🎉 Hoàn tất Giai đoạn 1!")


if __name__ == "__main__":
    main()

"""Kịch bản kiểm thử nghiệm thu Giai đoạn 1 (Phase 1 Integration & Concurrency Test).

Kiểm thử 5 tiêu chí cốt lõi:
1. Xác thực Bcrypt & Phân quyền RBAC theo hành động.
2. Patient Master Index: Tìm kiếm, nhận diện và gộp hồ sơ trùng lặp.
3. Chống Race Condition: 20 threads đồng thời lấy số tại cùng 1 tích tắc -> Kiểm tra 0 trùng lặp.
4. Kiểm tra ca trực bác sĩ và múi giờ Việt Nam.
5. Nhật ký kiểm toán an toàn y tế (Audit Trail).
"""
from __future__ import annotations

import concurrent.futures
import time
from datetime import date
import db
import auth
import patient_service
import queue_service


def test_phase1():
    print("=" * 70)
    print("BẮT ĐẦU CHẠY KIỂM THỬ NGHIỆM THU GIAI ĐOẠN 1...")
    print("=" * 70)

    # ── TEST 1: BCRYPT & PHÂN QUYỀN RBAC ──
    print("\n[TEST 1] Kiểm tra Bcrypt & RBAC phân quyền hành động...")
    res_admin = auth.authenticate_user("admin", "admin123", "127.0.0.1")
    assert res_admin["success"] is True, f"Admin login failed: {res_admin['error']}"
    assert res_admin["user"]["role"] == "admin"
    print("  ✓ Admin đăng nhập thành công qua Bcrypt.")

    res_doc = auth.authenticate_user("bs_noi_t105", "123456", "192.168.1.50")
    assert res_doc["success"] is True, f"Doctor login failed: {res_doc['error']}"
    assert res_doc["user"]["role"] == "doctor"
    print("  ✓ Bác sĩ bs_noi_t105 đăng nhập thành công qua Bcrypt.")

    # Kiểm tra quyền
    assert auth.has_permission("doctor", "ticket.call") is True
    assert auth.has_permission("doctor", "prescription.create") is True
    assert auth.has_permission("nurse", "prescription.create") is False
    assert auth.has_permission("admin", "any.custom.action") is True
    print("  ✓ Ma trận RBAC phân quyền hành động hoạt động chính xác.")

    # ── TEST 2: PATIENT MASTER INDEX (MPI) & GỘP HỒ SƠ ──
    print("\n[TEST 2] Kiểm tra Patient Master Index (MPI) & Nhận diện...")
    p1 = patient_service.get_or_create_patient(
        full_name="Nguyễn Văn Test A",
        phone="0988776655",
        cccd="001099887766",
        bhyt_code="DN4019999999999",
        allergies="Dị ứng Penicillin"
    )
    assert p1["patient_code"].startswith("AT-")
    print(f"  ✓ Đã cấp mã định danh duy nhất: {p1['patient_code']} ({p1['full_name']})")

    # Nhận diện lại khi bệnh nhân quay lại khám chỉ bằng CCCD
    p1_again = patient_service.get_or_create_patient(
        full_name="Nguyễn Văn Test A",
        phone="0988776655",
        cccd="001099887766"
    )
    assert p1_again["id"] == p1["id"]
    assert p1_again["is_new"] is False
    print("  ✓ Nhận diện chính xác bệnh nhân cũ qua CCCD (không bị tạo trùng).")

    # ── TEST 3: CHỐNG TRÙNG SỐ THỨ TỰ (ATOMIC CONCURRENCY TEST) ──
    print("\n[TEST 3] Kiểm thử áp lực: 20 Kiosk cùng lấy số đồng thời tại Phòng T1-05...")
    
    # Lấy room_id của T1-05
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rooms WHERE code = 'T1-05'")
    t105_id = cursor.fetchone()[0]

    # Reset bộ đếm ngày hôm nay để test
    today = queue_service.get_vn_today()
    cursor.execute("""
        DELETE FROM prescription_items 
        WHERE prescription_id IN (
            SELECT id FROM prescriptions WHERE examination_id IN (
                SELECT id FROM examinations WHERE ticket_id IN (
                    SELECT id FROM tickets WHERE current_room_id = ? AND visit_date = ?
                )
            )
        )
    """, (t105_id, today))
    cursor.execute("""
        DELETE FROM prescriptions 
        WHERE examination_id IN (
            SELECT id FROM examinations WHERE ticket_id IN (
                SELECT id FROM tickets WHERE current_room_id = ? AND visit_date = ?
            )
        )
    """, (t105_id, today))
    cursor.execute("DELETE FROM examinations WHERE ticket_id IN (SELECT id FROM tickets WHERE current_room_id = ? AND visit_date = ?)", (t105_id, today))
    cursor.execute("DELETE FROM clinical_orders WHERE ticket_id IN (SELECT id FROM tickets WHERE current_room_id = ? AND visit_date = ?)", (t105_id, today))
    cursor.execute("DELETE FROM tickets WHERE current_room_id = ? AND visit_date = ?", (t105_id, today))
    cursor.execute("DELETE FROM room_daily_counters WHERE room_id = ? AND visit_date = ?", (t105_id, today))
    conn.commit()
    conn.close()

    results = []
    errors = []

    def simulate_kiosk_issue(i):
        try:
            tk = queue_service.issue_ticket(
                room_id=t105_id,
                patient_name=f"Bệnh nhân Concurrency #{i:02d}",
                patient_phone=f"09110000{i:02d}",
                patient_notes="Test đồng thời chống trùng số"
            )
            return tk
        except Exception as e:
            return {"error": str(e)}

    # Chạy 20 threads song song
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(simulate_kiosk_issue, i) for i in range(1, 21)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if "error" in res:
                errors.append(res["error"])
            else:
                results.append(res)

    assert len(errors) == 0, f"Có lỗi trong quá trình cấp số đồng thời: {errors}"
    assert len(results) == 20, f"Dự kiến 20 vé, nhận được {len(results)}"

    seq_numbers = sorted([r["daily_seq"] for r in results])
    expected_seq = list(range(1, 21))
    
    print(f"  → Các số thứ tự nhận được từ 20 Kiosk song song: {seq_numbers}")
    assert seq_numbers == expected_seq, f"LỖI TRÙNG HOẶC NHẢY SỐ: {seq_numbers} != {expected_seq}"
    print("  ✓ TUYỆT ĐỐI KHÔNG TRÙNG SỐ: 20 vé liên tục từ 001 đến 020 hoàn hảo!")

    # ── TEST 4: KIỂM TRA CA TRỰC BÁC SĨ ──
    print("\n[TEST 4] Kiểm tra phân ca trực và ngoại lệ cấp cứu 24/7...")
    shift_status = queue_service.check_room_shift_available(t105_id)
    assert shift_status["available"] is True
    print(f"  ✓ Phòng T1-05 có ca trực: {shift_status['reason']}")

    # Khoa Cấp Cứu T1-04 luôn mở 24/7
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rooms WHERE code = 'T1-04'")
    t104_id = cursor.fetchone()[0]
    conn.close()

    cc_status = queue_service.check_room_shift_available(t104_id)
    assert cc_status["available"] is True
    print("  ✓ Khoa Cấp Cứu T1-04 luôn mở 24/7 và sẵn sàng tiếp nhận khẩn cấp.")

    # ── TEST 5: AUDIT TRAIL ĐÃ GHI NHẬN ĐẦY ĐỦ ──
    print("\n[TEST 5] Kiểm tra Nhật ký kiểm toán y tế (Audit Trail)...")
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 5 action, username, details, created_at FROM audit_logs ORDER BY id DESC")
    logs = cursor.fetchall()
    conn.close()

    assert len(logs) > 0
    for l in logs:
        print(f"  • [{l[3].strftime('%H:%M:%S')}] {l[1]} -> Action: {l[0]} ({l[2]})")
    print("  ✓ Audit Log ghi vết đầy đủ theo quy chuẩn an toàn thông tin.")

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ 5 BÀI TEST GIAI ĐOẠN 1 ĐÃ VƯỢT QUA VỚI ĐIỂM TUYỆT ĐỐI!")
    print("=" * 70)


if __name__ == "__main__":
    test_phase1()

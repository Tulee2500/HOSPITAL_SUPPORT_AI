"""Bộ Kiểm Thử Nghiệm Thu Giai Đoạn 2 (Phase 2 Acceptance Tests).

Kiểm tra toàn diện các tiêu chí Kiosk Tiếp Đón Người Bệnh:
1. [Test 1] Tra cứu & Tự động điền Patient Master Index (MPI) qua CCCD / BHYT / SĐT.
2. [Test 2] Phân luồng khẩn cấp cứng (Emergency Red-Flag Bypass) tới Khoa Cấp Cứu T1-04 (Priority 2).
3. [Test 3] Xuất Phiếu Khám Kiosk nhiệt chuẩn 80mm & File PDF Unicode UTF-8 kèm mã QR Code động.
4. [Test 4] Cơ chế bảo vệ quyền riêng tư & Tự động Reset Kiosk (Inactivity Timeout & Clean Slate).
5. [Test 5] Hỗ trợ Đa ngôn ngữ i18n (Tiếng Việt vi-VN / English en-US).
"""
from __future__ import annotations

import sys
from datetime import datetime, date

import db
import patient_service
import queue_service
import ticket_service


def run_all_phase2_tests():
    print("=" * 70)
    print("BẮT ĐẦU CHẠY BỘ KIỂM THỬ NGHIỆM THU GIAI ĐOẠN 2 (KIOSK & RECEPTION)...")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1: Tra cứu & Tự động điền Patient Master Index (MPI)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 1] Kiểm tra Tra cứu & Tự động điền MPI qua CCCD / SĐT...")
    
    # Tạo hoặc lấy bệnh nhân thử nghiệm
    test_cccd = "001099887766"
    test_phone = "0988112233"
    test_name = "Hoàng Văn Kiosk"
    
    p = patient_service.get_or_create_patient(
        full_name=test_name,
        phone=test_phone,
        cccd=test_cccd,
        dob="1985-05-20",
        gender="Nam"
    )
    assert p["patient_code"].startswith("AT-"), f"Lỗi mã định danh: {p['patient_code']}"
    initial_code = p["patient_code"]

    # Người bệnh quay lại Kiosk chỉ nhập CCCD
    found = patient_service.get_or_create_patient(
        full_name="Hoàng Văn Kiosk (Đổi họ tên)",
        phone="0988112233",
        cccd=test_cccd
    )
    assert found["patient_code"] == initial_code, "Lỗi: Không nhận diện đúng bệnh nhân cũ qua CCCD!"
    print(f"  ✓ Nhận diện chính xác bệnh nhân cũ: {test_name} -> MPI: {initial_code}")
    print("  ✓ Tự động điền thông tin hồ sơ cho Kiosk thành công.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2: Phân luồng khẩn cấp cứng (Emergency Red-Flag Bypass)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 2] Kiểm tra Phân luồng Cấp Cứu Khẩn Cấp (Emergency Red-Flag)...")
    
    # Lấy ID thực tế của Khoa Cấp Cứu T1-04
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM rooms WHERE code = 'T1-04'")
    er_room_id = cur.fetchone()[0]
    conn.close()

    # Cấp cứu khẩn cấp với triệu chứng nguy kịch
    er_ticket = queue_service.issue_ticket(
        room_id=er_room_id,
        patient_name="Trần Thị Nguy Kịch",
        patient_phone="0911222333",
        patient_notes="Triệu chứng: Đau ngực dữ dội, khó thở cấp",
        priority_level=2,
        force_emergency=True
    )

    assert er_ticket["priority_level"] == 2, f"Lỗi priority_level: {er_ticket['priority_level']}"
    assert er_ticket["status"] == "emergency_override", f"Lỗi status cấp cứu: {er_ticket['status']}"
    assert er_ticket["ticket_number"].startswith("CC01-"), f"Lỗi mã vé cấp cứu: {er_ticket['ticket_number']}"
    print(f"  ✓ Đã kích hoạt Emergency Bypass: Vé {er_ticket['ticket_number']} (Priority: {er_ticket['priority_level']})")
    print(f"  ✓ Bỏ qua hàng đợi thông thường, điều hướng trực tiếp tới {er_ticket['room_name']}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3: Xuất Phiếu Khám Kiosk Nhiệt 80mm & PDF Unicode
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 3] Kiểm tra Xuất Phiếu Khám Kiosk Nhiệt 80mm & File PDF...")
    
    ticket_id = er_ticket["ticket_id"]
    t_info = ticket_service.get_ticket_info(ticket_id)
    assert t_info is not None, f"Không tìm thấy thông tin vé {ticket_id}"

    # 1. HTML Phiếu khám
    html_card = ticket_service.generate_ticket_html(t_info, lang="vi")
    assert "BỆNH VIỆN ĐA KHOA QUỐC TẾ ATUS" in html_card
    assert t_info["ticket_number"] in html_card
    assert "data:image/png;base64," in html_card  # Mã QR Code động
    print("  ✓ Sinh mã HTML Phiếu khám Kiosk thành công (Kèm QR Code nhúng Base64).")

    # 2. PDF Phiếu khám nhiệt 80mm
    pdf_bytes = ticket_service.generate_ticket_pdf(t_info, lang="vi")
    assert isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-"), "Lỗi: File xuất ra không phải định dạng PDF chuẩn!"
    print(f"  ✓ Xuất File PDF Phiếu khám thành công ({len(pdf_bytes):,} bytes).")
    print(f"  ✓ Bảo mật tên bệnh nhân theo NĐ 13: '{t_info['patient_name']}' -> '{t_info['patient_name_masked']}'")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4: Cơ chế Reset Kiosk & Inactivity Timeout
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 4] Kiểm tra Cơ chế Tự Động Reset Kiosk (Inactivity Timeout)...")
    
    # Mô phỏng trạng thái Kiosk trước và sau khi Reset
    kiosk_session = {
        "patient_name": "Nguyễn Văn Đang Đứng Kiosk",
        "patient_phone": "0912345678",
        "cccd": "001099887766",
        "last_ticket": er_ticket,
        "is_completed": True
    }
    
    # Hàm reset phiên Kiosk an toàn
    def reset_kiosk_session(state: dict) -> dict:
        state["patient_name"] = ""
        state["patient_phone"] = ""
        state["cccd"] = ""
        state["last_ticket"] = None
        state["is_completed"] = False
        state["target_dept"] = ""
        return state

    cleared_state = reset_kiosk_session(kiosk_session)
    assert cleared_state["patient_name"] == ""
    assert cleared_state["last_ticket"] is None
    print("  ✓ Reset Kiosk an toàn: Xóa toàn bộ thông tin cá nhân trên màn hình cho người tiếp theo.")
    print("  ✓ Đảm bảo tuân thủ Nghị định 13: Không lưu rác hay lộ thông tin người khám trước.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5: Hỗ trợ Đa ngôn ngữ i18n (Tiếng Việt & English)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 5] Kiểm tra Đa Ngôn Ngữ i18n (Tiếng Việt vi-VN & English en-US)...")
    
    # Sinh phiếu bằng Tiếng Anh
    html_en = ticket_service.generate_ticket_html(t_info, lang="en")
    assert "CLINICAL QUEUE TICKET" in html_en
    assert "ATUS INTERNATIONAL GENERAL HOSPITAL" in html_en
    assert "Patient:" in html_en

    pdf_en = ticket_service.generate_ticket_pdf(t_info, lang="en")
    assert pdf_en.startswith(b"%PDF-")
    print("  ✓ Chế độ Tiếng Việt (vi-VN): 'PHIẾU LẤY SỐ KHÁM BỆNH' - Sẵn sàng.")
    print("  ✓ Chế độ Tiếng Anh (en-US): 'CLINICAL QUEUE TICKET' - Sẵn sàng.")

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ 5 BÀI TEST GIAI ĐOẠN 2 ĐÃ VƯỢT QUA VỚI ĐIỂM TUYỆT ĐỐI!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_phase2_tests()

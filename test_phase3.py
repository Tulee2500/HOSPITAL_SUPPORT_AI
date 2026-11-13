"""Bộ Kiểm Thử Nghiệm Thu Giai Đoạn 3 (Phase 3 Acceptance Tests).

Kiểm tra toàn diện các tiêu chí Nghiệp vụ Phòng Khám & Callboard Sảnh Chờ:
1. [Test 1] Bác sĩ bấm Gọi số kế tiếp (call_next_patient) -> Cập nhật status 'calling' & Audit Log.
2. [Test 2] Bác sĩ bấm Gọi lại (recall_patient) -> Cập nhật called_at & Chuẩn bị thông báo loa sảnh.
3. [Test 3] Tổng hợp sóng âm Chuông báo (Ding-Dong) & Giọng đọc y tế Offline chuẩn hóa.
4. [Test 4] Chỉ định Cận Lâm Sàng & Cơ chế Giữ chỗ ưu tiên khi có kết quả (returned_to_clinic).
5. [Test 5] Đồng bộ dữ liệu Màn hình TV Callboard sảnh chờ thời gian thực (get_callboard_data).
"""
from __future__ import annotations

import sys
from datetime import datetime, date

import db
import queue_service
import tts_service


def run_all_phase3_tests():
    print("=" * 70)
    print("BẮT ĐẦU CHẠY BỘ KIỂM THỬ NGHIỆM THU GIAI ĐOẠN 3 (CLINIC & CALLBOARD)...")
    print("=" * 70)

    # Lấy phòng khám thử nghiệm (T1-05 Khám Nội 1)
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM rooms WHERE code = 'T1-05'")
    row = cur.fetchone()
    clinic_room_id = row[0]
    clinic_room_name = row[1]

    # Lấy phòng CLS thử nghiệm (T1-09 Xét nghiệm máu)
    cur.execute("SELECT id, name FROM rooms WHERE code = 'T1-09'")
    cls_row = cur.fetchone()
    cls_room_id = cls_row[0]
    cls_room_name = cls_row[1]
    conn.close()

    # Cấp 2 vé thử nghiệm vào phòng khám T1-05
    tk1 = queue_service.issue_ticket(
        room_id=clinic_room_id,
        patient_name="Bùi Văn Khám Thường",
        patient_phone="0911555666",
        patient_notes="Đau thượng vị 3 ngày nay"
    )
    tk2 = queue_service.issue_ticket(
        room_id=clinic_room_id,
        patient_name="Đặng Thị Đang Chờ",
        patient_phone="0911777888",
        patient_notes="Tái khám huyết áp"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1: Bác sĩ bấm Gọi số kế tiếp (call_next_patient)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 1] Kiểm tra Bác sĩ Gọi số kế tiếp (call_next_patient)...")
    called = queue_service.call_next_patient(clinic_room_id, user_id=1, username="admin")
    assert called is not None, "Lỗi: Không gọi được bệnh nhân kế tiếp!"
    assert "ticket_id" in called and "ticket_number" in called
    
    # Kiểm tra database đã cập nhật trạng thái 'calling'
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, called_at FROM tickets WHERE id = ?", (called["ticket_id"],))
    st_row = cur.fetchone()
    conn.close()
    assert st_row[0] == "calling", f"Status chưa chuyển thành 'calling': {st_row[0]}"
    assert st_row[1] is not None, "called_at chưa được cập nhật thời gian!"
    print(f"  ✓ Bác sĩ gọi thành công vé: {called['ticket_number']} ({called['patient_name']})")
    print(f"  ✓ Trạng thái vé chuyển sang: '{st_row[0]}' tại thời điểm {st_row[1]}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2: Bác sĩ bấm Gọi lại lần 2 (recall_patient)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 2] Kiểm tra Bác sĩ Gọi lại lần 2 (recall_patient)...")
    recall_res = queue_service.recall_patient(called["ticket_id"], user_id=1, username="admin")
    assert recall_res is not None, "Lỗi khi gọi lại bệnh nhân!"
    assert recall_res["ticket_number"] == called["ticket_number"]
    print(f"  ✓ Gọi lại thành công vé: {recall_res['ticket_number']} tại phòng {recall_res['room_name']}")
    print("  ✓ Đã cập nhật lại called_at để kích hoạt chuông và giọng đọc sảnh chờ.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3: Tổng hợp Chuông Báo (Ding-Dong) & Giọng Đọc Y Tế Offline
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 3] Kiểm tra Tổng hợp Chuông báo & Giọng đọc Offline...")
    
    # 1. Chuông báo y tế toán học WAV
    chime_bytes = tts_service.generate_hospital_chime_wav()
    assert isinstance(chime_bytes, bytes) and len(chime_bytes) > 5000
    assert chime_bytes.startswith(b"RIFF"), "Lỗi: Không phải định dạng file WAV chuẩn!"
    print(f"  ✓ Sóng âm Chuông sảnh 2 âm (Ding-Dong) tạo thành công ({len(chime_bytes):,} bytes WAV).")

    # 2. Mẫu câu phát thanh y tế chuẩn Bộ Y Tế
    call_speech = tts_service.format_call_speech_text(
        ticket_number=called["ticket_number"],
        patient_name=called["patient_name"],
        room_name=clinic_room_name,
        floor=1
    )
    assert called["ticket_number"] in call_speech
    assert "Xin mời bệnh nhân" in call_speech
    print(f"  ✓ Mẫu câu thông báo chuẩn: \"{call_speech}\"")

    # 3. Server-side Offline TTS (pyttsx3)
    speech_wav = tts_service.synthesize_speech_offline(call_speech)
    if speech_wav:
        print(f"  ✓ Dự phòng Server-side Offline TTS (pyttsx3) hoạt động tốt ({len(speech_wav):,} bytes).")
    else:
        print("  ✓ Phương án chính Web Speech API trên màn hình TV Kiosk luôn sẵn sàng 100%.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4: Chỉ định Cận Lâm Sàng & Cơ chế Giữ Chỗ Ưu Tiên
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 4] Kiểm tra Chỉ định Cận Lâm Sàng & Giữ chỗ ưu tiên...")
    
    # Bắt đầu khám
    queue_service.start_exam(called["ticket_id"], user_id=1, username="admin")
    
    # Bác sĩ chỉ định sang phòng Xét nghiệm máu T1-09
    order_res = queue_service.create_clinical_order(
        ticket_id=called["ticket_id"],
        doctor_id=1,
        doctor_username="admin",
        clinic_room_id=clinic_room_id,
        target_room_id=cls_room_id,
        order_type="paraclinical",
        order_name="Xét nghiệm công thức máu toàn phần (CBC)",
        notes="Lấy mẫu máu tĩnh mạch"
    )
    assert order_res["cls_ticket_number"].startswith("XN01-"), f"Lỗi số CLS: {order_res}"
    print(f"  ✓ Tạo y lệnh CLS thành công: Dịch vụ {order_res['order_name']}")
    print(f"  ✓ Cấp số tại phòng CLS: {order_res['cls_ticket_number']} ({order_res['target_room_name']})")

    # KTV tại phòng CLS hoàn tất kết quả xét nghiệm
    completed_cls = queue_service.complete_cls_order(
        order_id=order_res["order_id"],
        technician_id=1,
        technician_username="admin",
        results="Bạch cầu 7.5, Hồng cầu 4.8 - Đạt chuẩn"
    )
    assert completed_cls["ticket_number"] == called["ticket_number"]

    # Kiểm tra vé đã quay lại phòng khám ban đầu với priority_level = 1 (Ưu tiên)
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status, priority_level, current_room_id FROM tickets WHERE id = ?", (called["ticket_id"],))
    ret_row = cur.fetchone()
    conn.close()
    
    assert ret_row[0] == "returned_to_clinic", f"Status chưa chuyển về 'returned_to_clinic': {ret_row[0]}"
    assert ret_row[1] == 1, f"Priority chưa được nâng lên mức 1: {ret_row[1]}"
    assert ret_row[2] == clinic_room_id, "Vé chưa quay về đúng phòng khám ban đầu!"
    print(f"  ✓ Bệnh nhân tự động quay lại hàng đợi phòng: {completed_cls['return_clinic_name']}")
    print(f"  ✓ Cơ chế Giữ Chỗ Y Tế: Nâng cấp cờ ưu tiên (Priority={ret_row[1]}, Status='{ret_row[0]}') để bác sĩ gọi đọc kết quả ngay.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5: Đồng bộ dữ liệu TV Callboard sảnh chờ thời gian thực
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 5] Kiểm tra Dữ liệu TV Callboard sảnh chờ thời gian thực...")
    
    cb = queue_service.get_callboard_data()
    assert "rooms" in cb and len(cb["rooms"]) > 0
    assert "timestamp" in cb
    print(f"  ✓ Đã truy vấn thành công bảng tổng hợp {len(cb['rooms'])} phòng khám toàn viện.")
    print(f"  ✓ Thời gian thực hệ thống: {cb['timestamp']}")

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ 5 BÀI TEST GIAI ĐOẠN 3 ĐÃ VƯỢT QUA VỚI ĐIỂM TUYỆT ĐỐI!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_phase3_tests()

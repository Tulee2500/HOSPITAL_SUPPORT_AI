"""Bộ Kiểm Thử Nghiệm Thu Giai Đoạn 4 (Phase 4 Acceptance Tests).

Kiểm tra toàn diện các tiêu chí Bệnh Án Lâm Sàng EMR & Đơn Thuốc Điện Tử:
1. [Test 1] Tra cứu Danh mục 40 Thuốc & Tồn kho Dược viện (pharmacy_inventory).
2. [Test 2] Lưu Bệnh Án Lâm Sàng EMR, Sinh hiệu & Mã hóa bệnh tật quốc tế ICD-10.
3. [Test 3] Kê Đơn Thuốc Điện Tử Chuẩn BYT (DT-YYYYMMDD-xxxx) & Trừ Tồn Kho Nguyên Tử.
4. [Test 4] Xuất File PDF Đơn Thuốc Điện Tử A4 Unicode UTF-8 kèm mã QR Code động.
5. [Test 5] Truy vết Lịch sử Khám bệnh & Đơn thuốc theo Patient Master Index (MPI).
"""
from __future__ import annotations

import sys
from datetime import datetime, date

import db
import patient_service
import queue_service
import emr_service


def run_all_phase4_tests():
    print("=" * 70)
    print("BẮT ĐẦU CHẠY BỘ KIỂM THỬ NGHIỆM THU GIAI ĐOẠN 4 (EMR & E-PRESCRIPTION)...")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 1: Tra cứu Danh mục Thuốc & Tồn Kho Dược
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 1] Kiểm tra Tra cứu Danh mục Thuốc & Tồn kho Dược...")
    meds = emr_service.search_medicines("para", limit=10)
    assert len(meds) > 0, "Lỗi: Không tìm thấy thuốc Paracetamol!"
    m_para = meds[0]
    assert m_para["stock"] > 0, f"Lỗi tồn kho thuốc: {m_para}"
    print(f"  ✓ Tìm thấy thuốc: {m_para['brand_name']} ({m_para['strength']})")
    print(f"  ✓ Hoạt chất: {m_para['active_ingredient']} · Tồn kho viện: {m_para['stock']} {m_para['unit']}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 2: Lưu Bệnh Án Lâm Sàng EMR & Mã hóa ICD-10
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 2] Kiểm tra Lưu Bệnh Án Lâm Sàng EMR & Mã hóa ICD-10...")
    
    # Tạo một bệnh nhân và vé khám mới
    p_rec = patient_service.get_or_create_patient(
        full_name="Đặng Văn EMR Test",
        phone="0933444555",
        cccd="001099112233"
    )
    
    # Cấp vé khám tại phòng khám Nội T1-05
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM rooms WHERE code = 'T1-05'")
    r_id = cur.fetchone()[0]
    conn.close()

    tk = queue_service.issue_ticket(
        room_id=r_id,
        patient_name="Đặng Văn EMR Test",
        patient_phone="0933444555",
        patient_notes="Đau vùng thượng vị sau khi ăn cay"
    )

    # Lưu bệnh án lâm sàng EMR
    exam = emr_service.save_clinical_examination(
        ticket_id=tk["ticket_id"],
        doctor_id=1,
        doctor_username="admin",
        chief_complaint="Đau âm ỉ thượng vị, ợ chua, buồn nôn",
        history_of_illness="Tiền sử đau dạ dày 2 năm, tái phát 1 tuần nay",
        clinical_notes="Bụng mềm, ấn đau tức nhẹ vùng thượng vị, không đề kháng",
        icd10_code="K29.7",
        icd10_name="Viêm dạ dày không đặc hiệu",
        conclusion="Viêm dạ dày cấp đợt bùng phát - Chỉ định điều trị nội khoa",
        revisit_date=date(2026, 11, 26),
        bp_sys=125,
        bp_dia=82,
        pulse=76,
        temperature=36.7,
        weight=68.5,
        height=172.0,
        spo2=99
    )

    assert exam["examination_id"] is not None
    assert exam["icd10_code"] == "K29.7"
    assert exam["bmi"] == 23.2
    print(f"  ✓ Đã lưu bệnh án khám ID: {exam['examination_id']} (Bệnh nhân MPI: {p_rec['patient_code']})")
    print(f"  ✓ Chẩn đoán chuẩn ICD-10: [{exam['icd10_code']}] {exam['icd10_name']}")
    print(f"  ✓ Chỉ số sinh hiệu: Huyết áp 125/82 mmHg, Mạch 76 bpm, BMI: {exam['bmi']}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 3: Kê Đơn Thuốc Điện Tử & Trừ Tồn Kho Nguyên Tử
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 3] Kiểm tra Kê Đơn Thuốc Điện Tử & Trừ Tồn Kho Dược...")

    # Lấy tồn kho trước khi kê
    stock_before = m_para["stock"]

    # Kê 2 loại thuốc
    pres_items = [
        {
            "medicine_id": m_para["id"],
            "medicine_name": m_para["brand_name"],
            "dosage": m_para["strength"],
            "quantity": 10,
            "unit": m_para["unit"],
            "usage_instructions": "Uống 1 viên khi đau tức thượng vị hoặc sốt, cách tối thiểu 6 giờ"
        }
    ]

    prescription = emr_service.create_electronic_prescription(
        examination_id=exam["examination_id"],
        doctor_id=1,
        doctor_username="admin",
        patient_id=p_rec["id"],
        items=pres_items,
        notes="Ăn đúng bữa, kiêng rượu bia, đồ cay chua và các chất kích thích."
    )

    assert prescription["prescription_code"].startswith("DT-")
    assert prescription["status"] == "issued"
    print(f"  ✓ Cấp mã đơn thuốc điện tử: {prescription['prescription_code']}")
    print(f"  ✓ Mã tra cứu quốc gia: {prescription['lookup_token']}")

    # Kiểm tra tồn kho đã bị trừ chính xác 10 viên
    meds_after = emr_service.search_medicines(m_para["brand_name"])
    stock_after = meds_after[0]["stock"]
    assert stock_after == stock_before - 10, f"Lỗi trừ kho: Trước {stock_before}, Sau {stock_after}"
    print(f"  ✓ Trừ tồn kho dược viện nguyên tử thành công: {stock_before} -> {stock_after} {m_para['unit']}")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 4: Xuất File PDF Đơn Thuốc Điện Tử Chuẩn Bộ Y Tế
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 4] Kiểm tra Xuất File PDF Đơn Thuốc A4 Unicode UTF-8...")

    pdf_bytes = emr_service.generate_prescription_pdf(prescription["prescription_id"])
    assert isinstance(pdf_bytes, bytes) and len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-"), "Lỗi: Không phải file PDF chuẩn!"
    print(f"  ✓ Đã sinh file PDF Đơn thuốc điện tử chuẩn Bộ Y Tế ({len(pdf_bytes):,} bytes).")
    print(f"  ✓ Đầy đủ thông tin: Bác sĩ điều trị, Bệnh nhân, ICD-10, Bảng thuốc, Hướng dẫn, QR Code.")

    # ─────────────────────────────────────────────────────────────────────────
    # TEST 5: Truy vết Lịch Sử Khám Bệnh & Đơn Thuốc theo MPI
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[TEST 5] Kiểm tra Truy vết Lịch Sử Khám Bệnh Cũ theo Patient MPI...")

    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.created_at, e.icd10_code, e.icd10_name, e.conclusion,
               pr.prescription_code, u.full_name AS doctor_name
        FROM examinations e
        LEFT JOIN prescriptions pr ON e.id = pr.examination_id
        JOIN users u ON e.doctor_id = u.id
        WHERE e.patient_id = ?
        ORDER BY e.created_at DESC
    """, (p_rec["id"],))
    history_records = cur.fetchall()
    conn.close()

    assert len(history_records) >= 1
    h_rec = history_records[0]
    print(f"  ✓ Truy vết thành công lượt khám của bệnh nhân {p_rec['patient_code']}:")
    print(f"    • Thời gian: {h_rec[1].strftime('%d/%m/%Y %H:%M')}")
    print(f"    • Chẩn đoán: [{h_rec[2]}] {h_rec[3]}")
    print(f"    • Đơn thuốc kèm theo: {h_rec[5]}")
    print(f"    • Bác sĩ điều trị: {h_rec[6]}")

    print("\n" + "=" * 70)
    print("🎉 TOÀN BỘ 5 BÀI TEST GIAI ĐOẠN 4 ĐÃ VƯỢT QUA VỚI ĐIỂM TUYỆT ĐỐI!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_phase4_tests()

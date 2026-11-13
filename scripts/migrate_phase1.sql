-- =========================================================================
-- HỆ THỐNG CƠ SỞ DỮ LIỆU BỆNH VIỆN ATUS - GIAI ĐOẠN 1 (FOUNDATION MIGRATION)
-- Database: hospital_atus
-- =========================================================================

-- 1. NÂNG CẤP BẢNG KHOA (departments)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('departments') AND name = 'name_en')
BEGIN
    ALTER TABLE departments ADD name_en NVARCHAR(100) NULL, floor INT DEFAULT 1, working_hours NVARCHAR(100) NULL;
END
GO

-- 2. NÂNG CẤP BẢNG PHÒNG (rooms: Hỗ trợ 35 phòng T1-01 -> T3-08)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('rooms') AND name = 'name_en')
BEGIN
    ALTER TABLE rooms ADD 
        name_en NVARCHAR(100) NULL,
        is_restricted BIT DEFAULT 0,
        instructions_en NVARCHAR(255) NULL,
        capacity_beds INT DEFAULT 0;
END
GO

-- 3. BẢNG BỆNH NHÂN ĐỊNH DANH (patients: Patient Master Index - MPI)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'patients')
BEGIN
    CREATE TABLE patients (
        id INT IDENTITY(1,1) PRIMARY KEY,
        patient_code NVARCHAR(50) NOT NULL UNIQUE,      -- Mã BN duy nhất: AT-xxxxxx
        full_name NVARCHAR(100) NOT NULL,
        phone NVARCHAR(20) NOT NULL,
        cccd NVARCHAR(20) NULL,                         -- Căn cước công dân 12 số
        bhyt_code NVARCHAR(25) NULL,                    -- Mã thẻ BHYT 15 ký tự
        dob DATE NULL,
        gender NVARCHAR(10) NULL,                       -- 'Nam', 'Nữ', 'Khác'
        address NVARCHAR(255) NULL,
        allergies NVARCHAR(MAX) NULL,                   -- Tiền sử dị ứng (Penicillin, NSAIDs...)
        blood_type NVARCHAR(10) NULL,                   -- A, B, AB, O (+/-)
        emergency_contact NVARCHAR(100) NULL,           -- Tên & SĐT người nhà
        is_active BIT DEFAULT 1,
        merged_into_id INT NULL,                        -- Nếu hồ sơ gộp vào bệnh nhân khác
        created_at DATETIME2 DEFAULT GETDATE(),
        updated_at DATETIME2 DEFAULT GETDATE()
    );
    CREATE INDEX IX_patients_phone ON patients (phone);
    CREATE UNIQUE NONCLUSTERED INDEX UQ_patients_cccd ON patients (cccd) WHERE cccd IS NOT NULL;
    CREATE UNIQUE NONCLUSTERED INDEX UQ_patients_bhyt ON patients (bhyt_code) WHERE bhyt_code IS NOT NULL;
END
GO

-- 4. BẢNG LỊCH SỬ GỘP HỒ SƠ (patient_merges)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'patient_merges')
BEGIN
    CREATE TABLE patient_merges (
        id INT IDENTITY(1,1) PRIMARY KEY,
        source_patient_id INT NOT NULL,
        target_patient_id INT NOT NULL,
        reason NVARCHAR(255) NOT NULL,
        merged_by_user_id INT NULL,
        merged_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_merges_source FOREIGN KEY (source_patient_id) REFERENCES patients(id),
        CONSTRAINT FK_merges_target FOREIGN KEY (target_patient_id) REFERENCES patients(id)
    );
END
GO

-- 5. BẢNG BỘ ĐẾM SỐ THỨ TỰ HÀNG ĐỢI NGUYÊN TỬ (room_daily_counters)
-- Chống triệt để Race Condition: Dùng UPDATE ... OUTPUT nguyên tử trên cặp (room_id, visit_date)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'room_daily_counters')
BEGIN
    CREATE TABLE room_daily_counters (
        id INT IDENTITY(1,1) PRIMARY KEY,
        room_id INT NOT NULL,
        visit_date DATE NOT NULL,
        current_seq INT NOT NULL DEFAULT 0,
        updated_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT UQ_room_daily_counters UNIQUE (room_id, visit_date),
        CONSTRAINT FK_counter_room FOREIGN KEY (room_id) REFERENCES rooms(id)
    );
END
GO

-- 6. BẢNG LỊCH PHÂN CA TRỰC BÁC SĨ (doctor_schedules)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'doctor_schedules')
BEGIN
    CREATE TABLE doctor_schedules (
        id INT IDENTITY(1,1) PRIMARY KEY,
        doctor_id INT NOT NULL,
        room_id INT NOT NULL,
        work_date DATE NOT NULL,
        shift NVARCHAR(20) NOT NULL, -- 'morning' (07:00-11:30), 'afternoon' (13:00-17:00), 'night' (23:00-07:00), 'full_day'
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        max_patients INT DEFAULT 50,
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_sched_doctor FOREIGN KEY (doctor_id) REFERENCES users(id),
        CONSTRAINT FK_sched_room FOREIGN KEY (room_id) REFERENCES rooms(id),
        CONSTRAINT UQ_doctor_shift UNIQUE (doctor_id, work_date, shift)
    );
    CREATE INDEX IX_sched_room_date ON doctor_schedules (room_id, work_date, shift, is_active);
END
GO

-- 7. CẬP NHẬT BẢNG VÉ HÀNG ĐỢI (tickets)
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('tickets') AND name = 'patient_id')
BEGIN
    ALTER TABLE tickets ADD patient_id INT NULL, schedule_id INT NULL;
    ALTER TABLE tickets ADD CONSTRAINT FK_tickets_patient FOREIGN KEY (patient_id) REFERENCES patients(id);
    ALTER TABLE tickets ADD CONSTRAINT FK_tickets_schedule FOREIGN KEY (schedule_id) REFERENCES doctor_schedules(id);
END
GO

-- Ràng buộc chống trùng số thứ tự trong cùng phòng và ngày
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'UQ_ticket_room_date_seq')
BEGIN
    CREATE UNIQUE INDEX UQ_ticket_room_date_seq ON tickets (current_room_id, visit_date, daily_seq);
END
GO

-- 8. BẢNG DANH MỤC THUỐC (medicines)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'medicines')
BEGIN
    CREATE TABLE medicines (
        id INT IDENTITY(1,1) PRIMARY KEY,
        code NVARCHAR(50) NOT NULL UNIQUE,              -- Mã thuốc: TH-xxx
        brand_name NVARCHAR(150) NOT NULL,              -- Biệt dược: Panadol Extra, Augmentin 1g...
        active_ingredient NVARCHAR(150) NOT NULL,       -- Hoạt chất: Paracetamol, Amoxicillin/Clavulanate...
        strength NVARCHAR(50) NOT NULL,                 -- Hàm lượng: 500mg, 1000mg, 10mg...
        unit NVARCHAR(20) NOT NULL,                     -- Viên, Gói, Chai, Lọ, Ống...
        route NVARCHAR(50) NOT NULL,                    -- Đường dùng: Uống, Tiêm bắp, Tiêm tĩnh mạch, Bôi ngoài da...
        category NVARCHAR(100) NOT NULL,                -- Kháng sinh, Hạ sốt, Tim mạch, Tiêu hóa...
        unit_price DECIMAL(18, 2) DEFAULT 0,
        is_prescription_required BIT DEFAULT 1,
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT GETDATE()
    );
END
GO

-- 9. BẢNG TỒN KHO DƯỢC (pharmacy_inventory)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'pharmacy_inventory')
BEGIN
    CREATE TABLE pharmacy_inventory (
        id INT IDENTITY(1,1) PRIMARY KEY,
        medicine_id INT NOT NULL,
        quantity_in_stock INT NOT NULL DEFAULT 0,
        lot_number NVARCHAR(50) NOT NULL,
        expiry_date DATE NOT NULL,
        location NVARCHAR(50) DEFAULT N'Kho Nhà Thuốc T1-12',
        updated_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_inv_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id)
    );
END
GO

-- 10. BẢNG QUAN HỆ TƯƠNG TÁC THUỐC (drug_interactions: Rule Engine)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'drug_interactions')
BEGIN
    CREATE TABLE drug_interactions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        ingredient_a NVARCHAR(150) NOT NULL,
        ingredient_b NVARCHAR(150) NOT NULL,
        severity NVARCHAR(20) NOT NULL,                  -- 'CONTRAINDICATION' (Mức Đỏ), 'WARNING' (Mức Vàng)
        description NVARCHAR(MAX) NOT NULL,              -- Mô tả tương tác lâm sàng
        clinical_advice NVARCHAR(MAX) NOT NULL,          -- Hướng dẫn bác sĩ
        created_at DATETIME2 DEFAULT GETDATE()
    );
    CREATE INDEX IX_interactions_ingredients ON drug_interactions (ingredient_a, ingredient_b);
END
GO

-- 11. BẢNG HỒ SƠ KHÁM LÂM SÀNG (examinations: EMR Sheet)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'examinations')
BEGIN
    CREATE TABLE examinations (
        id INT IDENTITY(1,1) PRIMARY KEY,
        ticket_id INT NOT NULL,
        patient_id INT NOT NULL,
        doctor_id INT NOT NULL,
        room_id INT NOT NULL,
        
        -- Dấu hiệu sinh tồn (Vital Signs)
        pulse INT NULL,                                 -- Mạch (lần/phút)
        blood_pressure_sys INT NULL,                    -- Huyết áp tâm thu (mmHg)
        blood_pressure_dia INT NULL,                    -- Huyết áp tâm trương (mmHg)
        temperature DECIMAL(4, 1) NULL,                 -- Thân nhiệt (°C)
        weight DECIMAL(5, 2) NULL,                      -- Cân nặng (kg)
        height DECIMAL(5, 2) NULL,                      -- Chiều cao (cm)
        bmi DECIMAL(4, 1) NULL,                         -- BMI
        spo2 INT NULL,                                  -- SpO2 (%)
        
        -- Chẩn đoán & Quá trình bệnh
        chief_complaint NVARCHAR(MAX) NULL,             -- Lý do vào viện
        history_of_illness NVARCHAR(MAX) NULL,          -- Quá trình bệnh lý
        clinical_notes NVARCHAR(MAX) NULL,              -- Khám thực thể
        
        icd10_code NVARCHAR(50) NULL,                   -- Mã bệnh ICD-10 (VD: I10, J02, K29...)
        icd10_name NVARCHAR(255) NULL,                  -- Tên bệnh theo ICD-10
        conclusion NVARCHAR(MAX) NULL,                  -- Kết luận & Hướng điều trị
        revisit_date DATE NULL,                         -- Hẹn tái khám
        
        created_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_exam_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
        CONSTRAINT FK_exam_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
        CONSTRAINT FK_exam_doctor FOREIGN KEY (doctor_id) REFERENCES users(id),
        CONSTRAINT FK_exam_room FOREIGN KEY (room_id) REFERENCES rooms(id)
    );
END
GO

-- 12. BẢNG ĐƠN THUỐC ĐIỆN TỬ (prescriptions)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'prescriptions')
BEGIN
    CREATE TABLE prescriptions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        examination_id INT NOT NULL,
        patient_id INT NOT NULL,
        doctor_id INT NOT NULL,
        prescription_code NVARCHAR(50) NOT NULL UNIQUE, -- Mã đơn: DT-xxxxxx
        lookup_token NVARCHAR(64) NOT NULL UNIQUE,      -- Token ngẫu nhiên an toàn dùng sinh QR
        notes NVARCHAR(MAX) NULL,                       -- Lời dặn chung của bác sĩ
        status NVARCHAR(50) DEFAULT 'signed',           -- 'draft', 'signed', 'dispensed', 'cancelled'
        created_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_presc_exam FOREIGN KEY (examination_id) REFERENCES examinations(id),
        CONSTRAINT FK_presc_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
        CONSTRAINT FK_presc_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
    );
END
GO

-- 13. BẢNG CHI TIẾT ĐƠN THUỐC (prescription_items)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'prescription_items')
BEGIN
    CREATE TABLE prescription_items (
        id INT IDENTITY(1,1) PRIMARY KEY,
        prescription_id INT NOT NULL,
        medicine_id INT NOT NULL,
        medicine_name NVARCHAR(150) NOT NULL,
        dosage NVARCHAR(100) NOT NULL,                  -- VD: Sáng 1 viên, Tối 1 viên sau ăn
        quantity INT NOT NULL,
        unit NVARCHAR(20) NOT NULL,
        usage_instructions NVARCHAR(255) NULL,
        CONSTRAINT FK_pitem_prescription FOREIGN KEY (prescription_id) REFERENCES prescriptions(id),
        CONSTRAINT FK_pitem_medicine FOREIGN KEY (medicine_id) REFERENCES medicines(id)
    );
END
GO

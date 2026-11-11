-- =========================================================================
-- HỆ THỐNG CƠ SỞ DỮ LIỆU BỆNH VIỆN ATUS (MICROSOFT SQL SERVER)
-- Database: hospital_atus
-- =========================================================================

-- 1. BẢNG KHOA (departments)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'departments')
BEGIN
    CREATE TABLE departments (
        id INT IDENTITY(1,1) PRIMARY KEY,
        code NVARCHAR(50) NOT NULL UNIQUE,
        name NVARCHAR(100) NOT NULL,
        description NVARCHAR(255) NULL,
        created_at DATETIME2 DEFAULT GETDATE()
    );
END
GO

-- 2. BẢNG PHÒNG (rooms: phòng khám lâm sàng & phòng cận lâm sàng)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'rooms')
BEGIN
    CREATE TABLE rooms (
        id INT IDENTITY(1,1) PRIMARY KEY,
        code NVARCHAR(50) NOT NULL UNIQUE,
        name NVARCHAR(100) NOT NULL,
        room_number NVARCHAR(50) NOT NULL,
        floor INT NOT NULL,
        type NVARCHAR(50) NOT NULL, -- 'clinic' (phòng khám) | 'paraclinical' (cận lâm sàng)
        prefix NVARCHAR(10) NOT NULL, -- Tiền tố vé: 'PK301', 'PK302', 'CLS201', 'CLS202'...
        department_id INT NULL,
        instructions NVARCHAR(255) NULL,
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_rooms_departments FOREIGN KEY (department_id) REFERENCES departments(id)
    );
END
GO

-- 3. BẢNG NGƯỜI DÙNG & TÀI KHOẢN (users)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
BEGIN
    CREATE TABLE users (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(50) NOT NULL UNIQUE,
        password_hash NVARCHAR(255) NOT NULL,
        salt NVARCHAR(64) NOT NULL,
        full_name NVARCHAR(100) NOT NULL,
        role NVARCHAR(50) NOT NULL, -- 'admin', 'doctor', 'technician', 'manager'
        department_id INT NULL,
        room_id INT NULL,
        is_active BIT DEFAULT 1,
        failed_login_count INT DEFAULT 0,
        locked_until DATETIME2 NULL,
        created_at DATETIME2 DEFAULT GETDATE(),
        CONSTRAINT FK_users_departments FOREIGN KEY (department_id) REFERENCES departments(id),
        CONSTRAINT FK_users_rooms FOREIGN KEY (room_id) REFERENCES rooms(id)
    );
END
GO

-- 4. BẢNG VÉ / LƯỢT KHÁM HÀNG ĐỢI (tickets)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'tickets')
BEGIN
    CREATE TABLE tickets (
        id INT IDENTITY(1,1) PRIMARY KEY,
        ticket_number NVARCHAR(50) NOT NULL UNIQUE, -- VD: PK301-001, AT-12345
        daily_seq INT NOT NULL,                     -- Số thứ tự trong ngày của phòng đó
        patient_name NVARCHAR(100) NOT NULL,
        patient_phone NVARCHAR(50) NOT NULL,
        patient_notes NVARCHAR(MAX) NULL,
        
        initial_room_id INT NOT NULL,               -- Phòng khám ban đầu
        current_room_id INT NOT NULL,               -- Phòng hiện tại đang xếp hàng/đang khám
        
        status NVARCHAR(50) NOT NULL,               -- 'waiting', 'calling', 'in_progress', 'ordered_cls', 'cls_in_progress', 'returned_to_clinic', 'completed', 'skipped'
        priority_level INT DEFAULT 0,               -- 0: Thường, 1: Ưu tiên quay lại sau cận lâm sàng, 2: Cấp cứu
        
        visit_date DATE NOT NULL,
        created_at DATETIME2 DEFAULT GETDATE(),
        called_at DATETIME2 NULL,
        completed_at DATETIME2 NULL,
        
        CONSTRAINT FK_tickets_initial_room FOREIGN KEY (initial_room_id) REFERENCES rooms(id),
        CONSTRAINT FK_tickets_current_room FOREIGN KEY (current_room_id) REFERENCES rooms(id)
    );
END
GO

-- 5. BẢNG CHỈ ĐỊNH CẬN LÂM SÀNG (clinical_orders)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'clinical_orders')
BEGIN
    CREATE TABLE clinical_orders (
        id INT IDENTITY(1,1) PRIMARY KEY,
        ticket_id INT NOT NULL,
        doctor_id INT NOT NULL,
        clinic_room_id INT NOT NULL,
        target_room_id INT NOT NULL,              -- Phòng cận lâm sàng (lấy máu, đo hô hấp, X-quang...)
        order_type NVARCHAR(100) NOT NULL,        -- 'blood_test', 'respiratory_test', 'xray', 'mri', 'other'
        order_name NVARCHAR(200) NOT NULL,        -- Tên dịch vụ hiển thị
        cls_ticket_number NVARCHAR(50) NULL,      -- Số thứ tự cấp tại phòng CLS (VD: CLS201-001)
        notes NVARCHAR(MAX) NULL,
        results NVARCHAR(MAX) NULL,               -- Kết quả cận lâm sàng
        status NVARCHAR(50) NOT NULL,             -- 'pending', 'in_progress', 'completed', 'cancelled'
        created_at DATETIME2 DEFAULT GETDATE(),
        completed_at DATETIME2 NULL,
        
        CONSTRAINT FK_orders_tickets FOREIGN KEY (ticket_id) REFERENCES tickets(id),
        CONSTRAINT FK_orders_doctor FOREIGN KEY (doctor_id) REFERENCES users(id),
        CONSTRAINT FK_orders_clinic_room FOREIGN KEY (clinic_room_id) REFERENCES rooms(id),
        CONSTRAINT FK_orders_target_room FOREIGN KEY (target_room_id) REFERENCES rooms(id)
    );
END
GO

-- 6. BẢNG AUDIT LOGS (audit_logs)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'audit_logs')
BEGIN
    CREATE TABLE audit_logs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT NULL,
        username NVARCHAR(50) NULL,
        action NVARCHAR(100) NOT NULL,            -- 'LOGIN', 'LOGOUT', 'CALL_TICKET', 'COMPLETE_TICKET', 'CREATE_ORDER', 'FINISH_ORDER'...
        target_type NVARCHAR(50) NULL,
        target_id NVARCHAR(50) NULL,
        details NVARCHAR(MAX) NULL,
        ip_address NVARCHAR(50) NULL,
        created_at DATETIME2 DEFAULT GETDATE()
    );
END
GO

-- 7. BẢNG NHẬT KÝ TƯƠNG TÁC AI TIẾP ĐÓN (chat_analytics_logs)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'chat_analytics_logs')
BEGIN
    CREATE TABLE chat_analytics_logs (
        id INT IDENTITY(1,1) PRIMARY KEY,
        query_text NVARCHAR(MAX) NOT NULL,
        intent NVARCHAR(50) NOT NULL,             -- 'symptom', 'procedure', 'emergency', 'other'
        department NVARCHAR(100) NULL,
        is_emergency BIT DEFAULT 0,
        created_at DATETIME2 DEFAULT GETDATE()
    );
END
GO

-- TẠO INDEX TỐI ƯU TRUY VẤN HÀNG ĐỢI
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_tickets_room_date_status')
BEGIN
    CREATE INDEX IX_tickets_room_date_status ON tickets (current_room_id, visit_date, status, priority_level);
END
GO

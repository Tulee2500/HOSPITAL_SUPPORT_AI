import sys
import os
sys.path.insert(0, os.path.abspath("."))
import db

conn = db.get_db_connection()
cursor = conn.cursor()

# 1. Tìm các ràng buộc UNIQUE trên bảng patients
cursor.execute("""
    SELECT name, type_desc 
    FROM sys.key_constraints 
    WHERE parent_object_id = OBJECT_ID('patients') AND type = 'UQ'
""")
uq_constraints = cursor.fetchall()
print("Found UNIQUE constraints:", uq_constraints)

for (cname, _) in uq_constraints:
    print(f"Dropping constraint {cname}...")
    cursor.execute(f"ALTER TABLE patients DROP CONSTRAINT [{cname}]")

# 2. Xóa các index cũ nếu có
cursor.execute("""
    IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'UQ_patients_cccd' AND object_id = OBJECT_ID('patients'))
        DROP INDEX UQ_patients_cccd ON patients;
""")
cursor.execute("""
    IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'UQ_patients_bhyt' AND object_id = OBJECT_ID('patients'))
        DROP INDEX UQ_patients_bhyt ON patients;
""")

# 3. Tạo FILTERED UNIQUE INDEX (chỉ ép unique khi giá trị khác NULL)
print("Creating filtered unique indexes...")
cursor.execute("""
    CREATE UNIQUE NONCLUSTERED INDEX UQ_patients_cccd 
    ON patients (cccd) 
    WHERE cccd IS NOT NULL;
""")
cursor.execute("""
    CREATE UNIQUE NONCLUSTERED INDEX UQ_patients_bhyt 
    ON patients (bhyt_code) 
    WHERE bhyt_code IS NOT NULL;
""")

conn.commit()
conn.close()
print("Fixed patients unique constraints successfully!")

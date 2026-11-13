"""Thực thi file migration SQL trên Microsoft SQL Server hospital_atus."""
import db

if __name__ == "__main__":
    print("Executing scripts/migrate_phase1.sql...")
    db.execute_sql_file("scripts/migrate_phase1.sql")
    print("Migration Phase 1 executed successfully!")

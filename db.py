"""Module kết nối và quản lý cơ sở dữ liệu Microsoft SQL Server (hospital_atus).
"""
from __future__ import annotations

import os
import pyodbc
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Cấu hình MSSQL
SERVER = os.getenv("MSSQL_SERVER", ".\\SQLEXPRESS")
DATABASE = os.getenv("MSSQL_DATABASE", "hospital_atus")
USER = os.getenv("MSSQL_USER", "sa")
PASSWORD = os.getenv("MSSQL_PASSWORD", "123")
DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")

CONNECTION_STRING = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USER};"
    f"PWD={PASSWORD};"
    f"TrustServerCertificate=yes;"
)


def get_db_connection() -> pyodbc.Connection:
    """Tạo kết nối tới Microsoft SQL Server database hospital_atus."""
    return pyodbc.connect(CONNECTION_STRING, autocommit=False)


def execute_sql_file(file_path: str | Path) -> None:
    """Thực thi file script SQL (hỗ trợ phân tách các batch GO)."""
    import re
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file SQL: {file_path}")

    raw_sql = file_path.read_text(encoding="utf-8")
    # Tách batch theo dòng chứa riêng chữ GO
    batches = [b.strip() for b in re.split(r"^\s*GO\s*$", raw_sql, flags=re.MULTILINE) if b.strip()]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for batch in batches:
            cursor.execute(batch)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def test_connection() -> dict:
    """Kiểm tra trạng thái kết nối tới MS SQL Server."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION AS version, DB_NAME() AS current_db")
        row = cursor.fetchone()
        conn.close()
        return {
            "success": True,
            "version": row[0],
            "database": row[1]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    res = test_connection()
    if res["success"]:
        print("✅ Kết nối MS SQL Server thành công!")
        print("Database:", res["database"])
        print("Version:", res["version"].splitlines()[0])
    else:
        print("❌ Kết nối thất bại:", res["error"])

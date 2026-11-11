"""Script chuyển tiếp / khởi chạy mặc định:
Người dùng có thể chọn khởi chạy Kiosk Bệnh Nhân (mặc định),
hoặc chạy các cổng chuyên biệt:
  - Cổng Bệnh nhân (User):  streamlit run app_user.py --server.port 8501
  - Cổng Nhân viên (Staff): streamlit run app_staff.py --server.port 8502
  - Cổng Quản trị (Admin):  streamlit run app_admin.py --server.port 8503
  - REST API Swagger Docs:   python api_server.py
"""
import runpy
runpy.run_path("app_user.py")

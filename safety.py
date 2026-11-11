"""BƯỚC 1 - Kiểm tra khẩn cấp bằng luật. Chạy trước mọi thứ, không tốn tiền API.
Nguyên tắc: thà báo nhầm còn hơn bỏ sót."""
import re
import unicodedata


def normalize(text: str) -> str:
    """Chữ thường + bỏ dấu tiếng Việt, để 'Khó thở' và 'kho tho' coi như nhau."""
    text = text.lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


# Mỗi luật là 1 tuple: TẤT CẢ các cụm trong tuple phải xuất hiện thì mới báo khẩn cấp.
EMERGENCY_RULES = [
    # hô hấp
    ("kho tho",), ("khong tho",), ("ngat tho",), ("tim tai",),
    # tim mạch
    ("dau nguc", "du doi"), ("dau nguc", "lan"), ("dau nguc", "mo hoi"),
    ("tuc nguc", "mo hoi"), ("nguc", "tay trai"),
    ("dau nguc",),  # đau ngực nói chung: chấp nhận báo nhầm để an toàn
    # đột quỵ
    ("meo mieng",), ("noi ngong",), ("yeu mot ben",), ("liet nua nguoi",), ("te mot ben",),
    # mất ý thức, co giật
    ("bat tinh",), ("bi ngat",), ("ngat xiu",), ("ngat di",), ("hon me",),
    ("co giat",), ("giat co",),
    # chảy máu
    ("non ra mau",), ("ho ra mau",), ("di ngoai ra mau",), ("chay mau", "khong cam"),
    # khác
    ("ngo doc",), ("uong nham",), ("tai nan",), ("dau bung du doi",),
    # tâm lý khủng hoảng
    ("tu tu",), ("tu sat",), ("muon chet",), ("khong muon song",), ("chang muon song",), ("chan song",), ("ket thuc cuoc doi",),
]

EMERGENCY_MESSAGE = (
    "⚠️ **Những gì bạn mô tả có thể là dấu hiệu nguy hiểm.**\n\n"
    "Vui lòng **gọi cấp cứu 115 hoặc đến ngay cơ sở cấp cứu gần nhất**, "
    "đừng chờ đặt lịch khám. Nếu đang ở bệnh viện, hãy báo ngay cho nhân viên "
    "tại quầy tiếp đón hoặc khoa cấp cứu. Nếu có người bên cạnh, hãy nhờ họ đi cùng bạn.\n\n"
    "_Trợ lý này không thể đánh giá tình trạng cấp cứu thay cho nhân viên y tế._"
)


def check_emergency_rules(message: str):
    """Trả về luật khớp (tuple) nếu có dấu hiệu khẩn cấp, ngược lại trả về None."""
    text = normalize(message)
    for rule in EMERGENCY_RULES:
        if all(phrase in text for phrase in rule):
            return rule
    return None

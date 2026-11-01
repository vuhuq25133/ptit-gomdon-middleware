"""
Module Trích xuất Thông tin Đơn hàng từ Tin nhắn Chat (Task 2.3)
==============================================================
Chịu trách nhiệm bóc tách tự động:
1. Số điện thoại (Regex 10 số đầu mạng VN: 03x, 05x, 07x, 08x, 09x, hỗ trợ cả dấu chấm, gạch ngang, khoảng trắng)
2. Địa chỉ nhận hàng & Tỉnh / Thành phố
3. Sản phẩm gợi ý (SKU, Màu sắc, Kích cỡ, Số lượng, Đơn giá)

Mô hình: Trợ lý bóc tách thông minh (Pre-fill Draft Order) phục vụ duyệt đơn bán tự động (Human-in-the-loop).
"""
import re
from typing import Dict, Any, List, Optional, Tuple

# Danh mục SKU và sản phẩm mặc định của hệ thống
PRODUCT_CATALOG = {
    "POLO-BLK-L": {"name": "Áo Polo Cotton Đen - Size L", "price": 250000.0, "type": "polo", "color": "BLK", "size": "L"},
    "POLO-BLK-M": {"name": "Áo Polo Cotton Đen - Size M", "price": 250000.0, "type": "polo", "color": "BLK", "size": "M"},
    "POLO-WHT-L": {"name": "Áo Polo Cotton Trắng - Size L", "price": 250000.0, "type": "polo", "color": "WHT", "size": "L"},
    "POLO-WHT-M": {"name": "Áo Polo Cotton Trắng - Size M", "price": 250000.0, "type": "polo", "color": "WHT", "size": "M"},
    "POLO-NVY-XL": {"name": "Áo Polo Cotton Navy - Size XL", "price": 250000.0, "type": "polo", "color": "NVY", "size": "XL"},
    "JEAN-BLU-31": {"name": "Quần Bò Nam Xanh - Size 31", "price": 350000.0, "type": "jean", "color": "BLU", "size": "31"},
    "JEAN-BLU-30": {"name": "Quần Bò Nam Xanh - Size 30", "price": 350000.0, "type": "jean", "color": "BLU", "size": "30"},
    "JEAN-BLU-32": {"name": "Quần Bò Nam Xanh - Size 32", "price": 350000.0, "type": "jean", "color": "BLU", "size": "32"},
}

# Danh sách từ điển 34 tỉnh/thành phố sau sáp nhập (Nghị quyết 202/2025/QH15)
PROVINCES = [
    # 6 Thành phố trực thuộc Trung ương
    ("Hà Nội", ["hà nội", "ha noi", "hn"]),
    ("Hồ Chí Minh", ["hồ chí minh", "hcm", "tp hcm", "tp.hcm", "tphcm", "sài gòn", "sai gon", "bình dương", "binh duong", "bà rịa", "ba ria", "vũng tàu", "vung tau"]),
    ("Hải Phòng", ["hải phòng", "hai phong", "hp", "hải dương", "hai duong"]),
    ("Đà Nẵng", ["đà nẵng", "da nang", "đn", "dn", "quảng nam", "quang nam"]),
    ("Cần Thơ", ["cần thơ", "can tho", "sóc trăng", "soc trang", "hậu giang", "hau giang"]),
    ("Huế", ["thừa thiên huế", "thua thien hue", "huế", "hue"]),

    # 28 Tỉnh sau sắp xếp
    ("An Giang", ["an giang", "kiên giang", "kien giang", "phú quốc", "phu quoc"]),
    ("Bắc Ninh", ["bắc ninh", "bac ninh", "bắc giang", "bac giang"]),
    ("Cà Mau", ["cà mau", "ca mau", "bạc liêu", "bac lieu"]),
    ("Cao Bằng", ["cao bằng", "cao bang"]),
    ("Điện Biên", ["điện biên", "dien bien"]),
    ("Đắk Lắk", ["đắk lắk", "dak lak", "đắc lắc", "dac lac", "phú yên", "phu yen"]),
    ("Đồng Nai", ["đồng nai", "dong nai", "bình phước", "binh phuoc"]),
    ("Đồng Tháp", ["đồng tháp", "dong thap", "tiền giang", "tien giang", "mỹ tho", "my tho"]),
    ("Gia Lai", ["gia lai", "bình định", "binh dinh", "quy nhơn", "quy nhon"]),
    ("Hà Tĩnh", ["hà tĩnh", "ha tinh"]),
    ("Hưng Yên", ["hưng yên", "hung yen", "thái bình", "thai binh"]),
    ("Khánh Hòa", ["khánh hòa", "khanh hoa", "nha trang", "ninh thuận", "ninh thuan", "phan rang"]),
    ("Lai Châu", ["lai châu", "lai chau"]),
    ("Lạng Sơn", ["lạng sơn", "lang son"]),
    ("Lào Cai", ["lào cai", "lao cai", "sa pa", "sapa", "yên bái", "yen bai"]),
    ("Lâm Đồng", ["lâm đồng", "lam dong", "đà lạt", "da lat", "đắk nông", "dak nong", "bình thuận", "binh thuan", "phan thiết", "phan thiet"]),
    ("Nghệ An", ["nghệ an", "nghe an", "vinh"]),
    ("Ninh Bình", ["ninh bình", "ninh binh", "hà nam", "ha nam", "nam định", "nam dinh"]),
    ("Phú Thọ", ["phú thọ", "phu tho", "vĩnh phúc", "vinh phuc", "hòa bình", "hoa binh"]),
    ("Quảng Ngãi", ["quảng ngãi", "quang ngai", "kon tum", "kontum"]),
    ("Quảng Ninh", ["quảng ninh", "quang ninh", "hạ long", "ha long"]),
    ("Quảng Trị", ["quảng trị", "quang tri", "quảng bình", "quang binh", "đồng hới", "dong hoi"]),
    ("Sơn La", ["sơn la", "son la", "mộc châu", "moc chau"]),
    ("Tây Ninh", ["tây ninh", "tay ninh", "long an", "tân an", "tan an"]),
    ("Thái Nguyên", ["thái nguyên", "thai nguyen", "bắc kạn", "bac kan", "bắc cạn"]),
    ("Thanh Hóa", ["thanh hóa", "thanh hoa"]),
    ("Tuyên Quang", ["tuyên quang", "tuyen quang", "hà giang", "ha giang"]),
    ("Vĩnh Long", ["vĩnh long", "vinh long", "bến tre", "ben tre", "trà vinh", "tra vinh"]),
]


def extract_phone(text: str) -> Optional[str]:
    """
    Bóc tách và chuẩn hóa Số điện thoại di động Việt Nam.
    Hỗ trợ các định dạng:
    - 0905111222
    - 0905.111.222 / 0905-111-222 / 0905 111 222
    - +84905111222 / 84905111222
    """
    if not text:
        return None

    # Pattern bao quát các biến thể dấu cách, chấm, gạch
    pattern = r"(?:(?:\+84|84|0)[35789])(?:[\s.-]?\d){8}\b"
    matches = re.findall(pattern, text)

    if not matches:
        return None

    # Lấy số đầu tiên tìm thấy và chuẩn hóa về dạng 09xxxxxxxx (10 chữ số)
    raw_phone = matches[0]
    digits = re.sub(r"\D", "", raw_phone)

    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]

    if len(digits) == 10 and digits.startswith(("03", "05", "07", "08", "09")):
        return digits

    return None


def extract_city(address_text: str) -> Optional[str]:
    """Nhận diện tên Tỉnh/Thành phố từ đoạn địa chỉ"""
    if not address_text:
        return None

    text_lower = address_text.lower()
    for standard_name, aliases in PROVINCES:
        for alias in aliases:
            # So khớp theo từ nguyên vẹn
            if re.search(r"\b" + re.escape(alias) + r"\b", text_lower):
                return standard_name

    return None


def extract_address(text: str, detected_phone: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Bóc tách Địa chỉ nhận hàng và Tỉnh/Thành phố.
    Quét đoạn văn bản sau các tiền tố thông dụng: 'đ/c', 'đc', 'địa chỉ', 'ship đến', 'ship về', 'về'...
    Hỗ trợ cả tên toà nhà, chung cư (HH2A, CT1, P302,...) và từ đệm không dấu 'nhe'.
    """
    if not text:
        return None, None

    # Các từ khóa nhận diện bắt đầu đoạn địa chỉ
    address_prefixes = [
        r"(?:đ/c|đc|địa chỉ|dia chi)\s*[:：\-]?\s*",
        r"(?:ship\s*(?:đến|về|qua)|gửi\s*(?:đến|về|qua)|giao\s*(?:đến|về|qua))\s*[:：\-]?\s*",
        r"\b(?:về|ve)\s+([A-Za-z0-9]+[/\w\s,]+)",
    ]

    extracted = None

    # Thử khớp các tiền tố mạnh: 'đ/c:', 'địa chỉ:', 'ship về:'
    for prefix in address_prefixes[:2]:
        match = re.search(prefix + r"([^.;\n]+)", text, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            break

    # Nếu chưa bắt được, thử khớp tiền tố 'về <toà nhà/số nhà>...'
    if not extracted:
        match = re.search(r"\b(?:về|ve)\s+([A-Za-z0-9]+[\w\s,/-]+?)(?=(?:sđt|sdt|phone|nhé|nhe|nha|ạ|$))", text, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()

    if not extracted:
        return None, None

    # Làm sạch địa chỉ: Loại bỏ phần SĐT nếu vô tình bị dính vào đuôi
    if detected_phone:
        extracted = extracted.replace(detected_phone, "")

    # Cắt bỏ các từ khóa SĐT hoặc từ đệm cuối câu
    cleanup_patterns = [
        r"(?:sđt|sdt|số|phone|đt|tel)\s*[:：\-]?\s*\d*",
        r"\b(?:nhé|nha|ạ|nhe|nhé shop|nha shop|nhe shop|nha bạn|nhé bạn|nhe bạn)\b.*$",
    ]
    for cp in cleanup_patterns:
        extracted = re.sub(cp, "", extracted, flags=re.IGNORECASE)

    extracted = extracted.strip(" ,.-:;").strip()

    # Kiểm tra độ dài hợp lý của địa chỉ (ít nhất 5 ký tự)
    if len(extracted) < 5:
        return None, None

    city = extract_city(extracted)
    return extracted, city


def extract_items(text: str) -> List[Dict[str, Any]]:
    """
    Bóc tách sản phẩm, màu sắc, size, số lượng và quy đổi sang SKU hệ thống.
    """
    if not text:
        return []

    text_lower = text.lower()

    # 1. Bóc tách số lượng (mặc định là 1)
    quantity = 1
    qty_match = re.search(r"(\d+)\s*(?:áo|cái|chiếc|quần|bộ|đôi|hộp|sp)\b", text_lower)
    if qty_match:
        try:
            quantity = max(1, int(qty_match.group(1)))
        except ValueError:
            quantity = 1
    else:
        # Kiểm tra từ khóa: đặt 1, lấy 2, mua 1...
        qty_action = re.search(r"(?:đặt|lấy|mua|ship)\s+(\d+)\b", text_lower)
        if qty_action:
            try:
                quantity = max(1, int(qty_action.group(1)))
            except ValueError:
                quantity = 1

    # 2. Phân loại ngành hàng: Quần bò / Jean hay Áo Polo
    if any(k in text_lower for k in ["quần bò", "quan bo", "quần jean", "quan jean", "jean", "bò"]):
        # Bóc size quần: 29, 30, 31, 32...
        size_match = re.search(r"(?:size|sz|số)\s*(2[8-9]|3[0-6])\b", text_lower)
        size = size_match.group(1) if size_match else "31"

        sku = f"JEAN-BLU-{size}"
        if sku not in PRODUCT_CATALOG:
            sku = "JEAN-BLU-31"

        product_meta = PRODUCT_CATALOG[sku]
        return [{
            "sku": sku,
            "name": product_meta["name"],
            "quantity": quantity,
            "unit_price": product_meta["price"]
        }]

    if any(k in text_lower for k in ["áo polo", "ao polo", "polo", "áo", "ao"]):
        # Bóc size áo: S, M, L, XL, XXL
        size_match = re.search(r"\b(?:size|sz)\s*(s|m|l|xl|xxl|2xl)\b", text_lower)
        size = size_match.group(1).upper() if size_match else "L"
        if size == "2XL":
            size = "XL"

        # Bóc màu sắc: đen, trắng, navy
        color = "BLK"
        if any(w in text_lower for w in ["trắng", "trang", "white"]):
            color = "WHT"
        elif any(w in text_lower for w in ["navy", "xanh navy", "xanh than", "xanh"]):
            color = "NVY"

        sku = f"POLO-{color}-{size}"
        if sku not in PRODUCT_CATALOG:
            # Fallback về SKU phổ thông
            sku = f"POLO-{color}-L" if f"POLO-{color}-L" in PRODUCT_CATALOG else "POLO-BLK-L"

        product_meta = PRODUCT_CATALOG.get(sku, PRODUCT_CATALOG["POLO-BLK-L"])
        return [{
            "sku": sku,
            "name": product_meta["name"],
            "quantity": quantity,
            "unit_price": product_meta["price"]
        }]

    # Trường hợp không phát hiện được sản phẩm cụ thể
    return []


def extract_order_from_text(text: str) -> Dict[str, Any]:
    """
    Hàm tổng hợp chính (Main Facade):
    Tiếp nhận văn bản câu chat và bóc tách toàn bộ thông tin Đơn nháp.
    """
    if not text:
        return {
            "has_phone": False,
            "phone": None,
            "shipping_address": None,
            "shipping_city": None,
            "items": [],
            "total_amount": 0.0,
            "confidence_score": 0.0,
            "note": "Tin nhắn rỗng"
        }

    phone = extract_phone(text)
    address, city = extract_address(text, detected_phone=phone)
    items = extract_items(text)

    # Tính tổng tiền
    total_amount = sum(item["unit_price"] * item["quantity"] for item in items)

    # Đánh giá độ tin cậy của thuật toán (Confidence Score)
    confidence = 0.0
    if phone:
        confidence += 0.5  # Bắt được SĐT đóng góp 50% độ tin cậy
    if address:
        confidence += 0.3  # Bắt được địa chỉ đóng góp 30%
    if items:
        confidence += 0.2  # Bắt được sản phẩm đóng góp 20%

    return {
        "has_phone": bool(phone),
        "phone": phone,
        "shipping_address": address,
        "shipping_city": city,
        "items": items,
        "total_amount": total_amount,
        "confidence_score": round(confidence, 2),
        "note": "Trích xuất tự động từ câu chat khách hàng"
    }

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
from app.core.catalog import (
    PRODUCT_CATALOG,
    BASE_PRODUCTS,
    DEFAULT_MODEL_BY_CATEGORY,
    SIZES,
)

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

    # Pattern bao quát các biến thể dấu cách, chấm, gạch (kể cả khoảng trắng sau +84)
    pattern = r"(?:(?:\+84|84|0)[\s.-]?[35789])(?:[\s.-]?\d){8}\b"
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


# Các cụm từ phủ định / hủy đặt hàng
CANCEL_PATTERNS = [
    r"\b(?:không|khong|ko|k)\s+(?:mua|lấy|lay|đặt|dat|chốt|chot)\b",
    r"\b(?:hủy|huy)\s*(?:đơn|don|hàng|hang)?\b",
    r"\bthôi\s+(?:không|khong|ko)\b",
]


def is_cancel_or_negative_intent(text: str) -> bool:
    """Kiểm tra xem câu chat có mang ý định hủy đơn / từ chối mua hay không"""
    if not text:
        return False
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in CANCEL_PATTERNS)


def _extract_size_from_clause(clause_lower: str, default_size: str = "L") -> str:
    """Bóc tách size chuẩn S, M, L, XL, XXL từ mệnh đề"""
    size_match = re.search(r"\b(?:size|sz|cỡ|co)?\s*(xxl|2xl|xl|s|m|l)\b", clause_lower)
    if size_match:
        # Ưu tiên bắt trường hợp có chữ 'size/sz' đứng trước hoặc đứng độc lập cuối mệnh đề
        explicit = re.search(r"\b(?:size|sz|cỡ|co)\s*(xxl|2xl|xl|s|m|l)\b", clause_lower)
        raw_sz = (explicit.group(1) if explicit else size_match.group(1)).upper()
        if raw_sz == "2XL":
            return "XXL"
        if raw_sz in SIZES:
            return raw_sz
    return default_size


def _extract_quantity_from_clause(clause_lower: str) -> int:
    """Bóc tách số lượng sản phẩm trong 1 mệnh đề"""
    # Loại bỏ tạm phần size/sđt/địa chỉ để không bắt nhầm số nhà hoặc mã áo (8, 0, 97, 98) làm số lượng
    cleaned = re.sub(r"\b(?:size|sz|cỡ|co)\s*(?:xxl|2xl|xl|s|m|l|30|31|32)\b", "", clause_lower)
    cleaned = re.sub(r"(?:(?:\+84|84|0)[35789])(?:[\s.-]?\d){8}\b", "", cleaned)

    qty_match = re.search(
        r"\b(\d{1,2})\s*(?:áo|ao|cái|cai|chiếc|chiec|quần|quan|bộ|bo|hộp|sp|mẫu|mau|hoodie|shirt|tee|jersey|jacket|longsleeve|windbreaker)\b",
        cleaned,
    )
    if qty_match:
        return max(1, int(qty_match.group(1)))

    qty_action = re.search(
        r"(?:đặt|dat|lấy|lay|mua|ship|cho|thêm|them)\s+(?:(?:mình|minh|em|anh|chị|chi|shop)\s+)?(\d{1,2})\b",
        cleaned,
    )
    if qty_action:
        return max(1, int(qty_action.group(1)))

    # Bắt số lượng đứng ngay đầu mệnh đề (VD: "2 Walker Core Hoodie size XL")
    leading_qty = re.match(r"^\s*(\d{1,2})\s+(?!(?:size|sz|sđt|sdt)\b)[a-zA-ZÀ-ỹ\"]", cleaned)
    if leading_qty:
        val = int(leading_qty.group(1))
        if 1 <= val <= 50:
            return val
    return 1


def _extract_single_clause_item(clause: str) -> Optional[Dict[str, Any]]:
    """Bóc tách 1 dòng sản phẩm từ 1 mệnh đề con"""
    clause_lower = clause.lower().strip()
    if not clause_lower or is_cancel_or_negative_intent(clause_lower):
        return None

    quantity = _extract_quantity_from_clause(clause_lower)
    size = _extract_size_from_clause(clause_lower, default_size="L")

    # 1. Kiểm tra nếu khách gõ trực tiếp mã SKU hoặc mã dòng Alan Walker (VD: AW-HOOD-WCH-XL hoặc AW-HOOD-WCH)
    sku_direct = re.search(r"\b(AW-[A-Z0-9]+-[A-Z0-9]+(?:-(?:XXL|XL|S|M|L))?)\b", clause.upper())
    if sku_direct:
        raw_code = sku_direct.group(1)
        if raw_code in PRODUCT_CATALOG:
            meta = PRODUCT_CATALOG[raw_code]
            return {"sku": raw_code, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}
        full_sku = f"{raw_code}-{size}"
        if full_sku in PRODUCT_CATALOG:
            meta = PRODUCT_CATALOG[full_sku]
            return {"sku": full_sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    # 2. So khớp từ khóa của 58 mẫu áo Alan Walker Store (ưu tiên cụm từ khóa dài & cụ thể nhất)
    best_base = None
    best_kw_len = 0
    for base in BASE_PRODUCTS:
        all_kws = [base["name"].lower().replace('"', "")] + [k.lower() for k in base.get("keywords", [])]
        for kw in all_kws:
            if kw in clause_lower and len(kw) > best_kw_len:
                best_base = base
                best_kw_len = len(kw)

    if best_base:
        sku = f"{best_base['code']}-{size}"
        meta = PRODUCT_CATALOG[sku]
        return {
            "sku": sku,
            "name": meta["name"],
            "quantity": quantity,
            "price": meta["price"],
            "unit_price": meta["price"],
        }

    # 3. So khớp theo 4 nhóm áo Alan Walker chung (hoodie, longsleeve, jacket, shirt/jersey/tee)
    if any(k in clause_lower for k in ["hoodie", "áo nỉ", "ao ni", "áo mũ", "ao mu"]):
        base_code = DEFAULT_MODEL_BY_CATEGORY["hoodie"]
        sku = f"{base_code}-{size}"
        meta = PRODUCT_CATALOG[sku]
        return {"sku": sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    if any(k in clause_lower for k in ["longsleeve", "long sleeve", "dài tay", "dai tay", "tay dài", "tay dai"]):
        base_code = DEFAULT_MODEL_BY_CATEGORY["longsleeve"]
        sku = f"{base_code}-{size}"
        meta = PRODUCT_CATALOG[sku]
        return {"sku": sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    if any(k in clause_lower for k in ["jacket", "windbreaker", "áo khoác", "ao khoac", "áo gió", "ao gio"]):
        base_code = DEFAULT_MODEL_BY_CATEGORY["jacket"]
        sku = f"{base_code}-{size}"
        meta = PRODUCT_CATALOG[sku]
        return {"sku": sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    if any(k in clause_lower for k in ["t-shirt", "tshirt", "tee", "jersey", "áo thun", "ao thun", "áo phông", "ao phong", "shirt"]):
        base_code = DEFAULT_MODEL_BY_CATEGORY["shirt"]
        sku = f"{base_code}-{size}"
        meta = PRODUCT_CATALOG[sku]
        return {"sku": sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    # 4. Giữ tương thích với Quần bò / Jean & Áo Polo truyền thống
    if any(k in clause_lower for k in ["quần bò", "quan bo", "quần jean", "quan jean", "jean", "bò"]):
        size_match = re.search(r"(?:size|sz|số)?\s*(30|31|32)\b", clause_lower)
        j_size = size_match.group(1) if size_match else "31"
        sku = f"JEAN-BLU-{j_size}"
        meta = PRODUCT_CATALOG[sku]
        return {"sku": sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    if any(k in clause_lower for k in ["áo polo", "ao polo", "polo", "áo", "ao"]):
        color = "BLK"
        if any(w in clause_lower for w in ["trắng", "trang", "white"]):
            color = "WHT"
        elif any(w in clause_lower for w in ["navy", "xanh navy", "xanh than", "xanh"]):
            color = "NVY"
        sku = f"POLO-{color}-{size}"
        if sku not in PRODUCT_CATALOG:
            sku = f"POLO-{color}-L"
        meta = PRODUCT_CATALOG[sku]
        return {"sku": sku, "name": meta["name"], "quantity": quantity, "price": meta["price"], "unit_price": meta["price"]}

    return None


def extract_items(text: str) -> List[Dict[str, Any]]:
    """
    Bóc tách danh sách sản phẩm (hỗ trợ nhiều mặt hàng trong 1 câu chat),
    phân biệt đủ 4 dòng Alan Walker (shirt, hoodie, longsleeve, jacket) + 5 size S..XXL,
    và tự động chặn câu phủ định / hủy đơn.
    """
    if not text or is_cancel_or_negative_intent(text):
        return []

    # Tách câu theo các liên từ nối sản phẩm: "và", "với", "kèm", "+", ";"
    clauses = re.split(r"\s+(?:và|va|với|voi|kèm|kem|\+)\s+|;|\n", text)
    extracted_list: List[Dict[str, Any]] = []

    for clause in clauses:
        item = _extract_single_clause_item(clause)
        if item:
            # Nếu trùng SKU trong cùng câu thì cộng dồn số lượng
            existing = next((x for x in extracted_list if x["sku"] == item["sku"]), None)
            if existing:
                existing["quantity"] += item["quantity"]
            else:
                extracted_list.append(item)

    return extracted_list


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
            "intent": "empty",
            "note": "Tin nhắn rỗng"
        }

    # Nếu khách nhắn hủy đơn / không mua nữa -> Tuyệt đối không sinh đơn nháp
    if is_cancel_or_negative_intent(text):
        return {
            "has_phone": False,
            "phone": None,
            "shipping_address": None,
            "shipping_city": None,
            "items": [],
            "total_amount": 0.0,
            "confidence_score": 0.0,
            "intent": "cancel",
            "note": "Khách báo hủy hoặc từ chối mua hàng"
        }

    phone = extract_phone(text)
    address, city = extract_address(text, detected_phone=phone)
    items = extract_items(text)

    # Tính tổng tiền chuẩn từ danh sách items
    total_amount = sum(item["unit_price"] * item["quantity"] for item in items)

    # Điểm hoàn thiện thông tin (Completeness / Confidence Score)
    confidence = 0.0
    if phone:
        confidence += 0.5  # Có SĐT: +50%
    if address:
        confidence += 0.3  # Có địa chỉ: +30%
    if items:
        confidence += 0.2  # Có sản phẩm: +20%

    return {
        "has_phone": bool(phone),
        "phone": phone,
        "shipping_address": address,
        "shipping_city": city,
        "items": items,
        "total_amount": total_amount,
        "confidence_score": round(confidence, 2),
        "intent": "order" if (phone or items) else "chat",
        "note": "Trích xuất tự động từ câu chat khách hàng"
    }

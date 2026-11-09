"""
Alan Walker Official Store Catalog & SKU Mapping Engine
=======================================================
Danh mục 58 mẫu áo từ store.alanwalker.com thuộc 4 phân loại:
- shirt (T-Shirts & Jerseys): 28 mẫu
- hoodie (Hoodies & Zip Hoodies): 23 mẫu
- longsleeve (Áo dài tay): 4 mẫu
- jacket (Áo khoác Windbreaker / Stage Jacket): 3 mẫu

Mỗi mẫu có 5 kích cỡ chuẩn: S, M, L, XL, XXL (Tổng cộng: 58 x 5 = 290 mã SKU chuẩn).
"""
from typing import Dict, Any, List, Optional

SIZES = ["S", "M", "L", "XL", "XXL"]

# 58 Mẫu áo gốc bóc tách từ 15 ảnh chụp store.alanwalker.com
BASE_PRODUCTS: List[Dict[str, Any]] = [
    # =========================================================================
    # 1. NHÓM SHIRT (T-Shirts & Jerseys - 28 mẫu)
    # =========================================================================
    {"code": "AW-SHIRT-WUTJ", "name": "Walkers United Team Jersey", "category": "shirt", "price": 636000.0,
     "keywords": ["walkers united team jersey", "walkers united", "team jersey", "united jersey"]},
    {"code": "AW-SHIRT-FPT", "name": "Faded Play T-shirt", "category": "shirt", "price": 331000.0,
     "keywords": ["faded play t-shirt", "faded play", "ao faded play"]},
    {"code": "AW-SHIRT-WOWA", "name": "World Of Walker Anniversary T-Shirt", "category": "shirt", "price": 596000.0,
     "keywords": ["world of walker anniversary", "anniversary t-shirt", "anniversary tee", "ao anniversary"]},
    {"code": "AW-SHIRT-WRLS", "name": "WRL Speed Logo T-shirt", "category": "shirt", "price": 596000.0,
     "keywords": ["wrl speed logo t-shirt", "wrl speed logo", "speed logo t-shirt", "speed logo tee"]},
    {"code": "AW-SHIRT-SST", "name": "Springseeker Sports T-shirt", "category": "shirt", "price": 702000.0,
     "keywords": ["springseeker sports t-shirt", "springseeker", "sports t-shirt"]},
    {"code": "AW-SHIRT-MCT", "name": '"Monster" Core T-Shirt', "category": "shirt", "price": 596000.0,
     "keywords": ["monster core t-shirt", "monster core tee", "ao monster core", "monster t-shirt"]},
    {"code": "AW-SHIRT-ROTD", "name": "Rise Of The Drone Vintage T-Shirt", "category": "shirt", "price": 596000.0,
     "keywords": ["rise of the drone", "rise of drone", "drone vintage t-shirt", "vintage t-shirt"]},
    {"code": "AW-SHIRT-ENCT", "name": "Encyclopedia T-shirt", "category": "shirt", "price": 768000.0,
     "keywords": ["encyclopedia t-shirt", "encyclopedia tee", "ao encyclopedia"]},
    {"code": "AW-SHIRT-WOW97", "name": "World of Walker '97' Jersey", "category": "shirt", "price": 768000.0,
     "keywords": ["world of walker 97 jersey", "97 jersey", "ao 97", "walker 97"]},
    {"code": "AW-SHIRT-W8HJ", "name": "Walker 8 Hockey Jersey", "category": "shirt", "price": 993000.0,
     "keywords": ["walker 8 hockey jersey", "8 hockey jersey", "hockey 8"]},
    {"code": "AW-SHIRT-W0HJ", "name": "Walker 0 Hockey Jersey", "category": "shirt", "price": 1297000.0,
     "keywords": ["walker 0 hockey jersey", "0 hockey jersey", "hockey 0"]},
    {"code": "AW-SHIRT-SLT", "name": "Snake Logo Tee", "category": "shirt", "price": 120000.0,
     "keywords": ["snake logo tee", "snake logo", "ao snake", "snake tee"]},
    {"code": "AW-SHIRT-CCTJ", "name": "Creator Circle - Tribe Jersey", "category": "shirt", "price": 662000.0,
     "keywords": ["creator circle", "creator circle tribe jersey"]},
    {"code": "AW-SHIRT-CPOTJ", "name": "CheckPoint One - Tribe Jersey", "category": "shirt", "price": 662000.0,
     "keywords": ["checkpoint one", "check point one", "checkpoint tribe jersey"]},
    {"code": "AW-SHIRT-UFTJ", "name": "Unity Force - Tribe Jersey", "category": "shirt", "price": 662000.0,
     "keywords": ["unity force", "unity force tribe jersey"]},
    {"code": "AW-SHIRT-DST", "name": "Drone Sketch T-shirt", "category": "shirt", "price": 847000.0,
     "keywords": ["drone sketch t-shirt", "drone sketch", "ao drone sketch"]},
    {"code": "AW-SHIRT-UWT", "name": "Unite Walkers T-shirt", "category": "shirt", "price": 847000.0,
     "keywords": ["unite walkers t-shirt", "unite walkers", "walkers join"]},
    {"code": "AW-SHIRT-WOWCT", "name": "World of Walker Core Tee", "category": "shirt", "price": 212000.0,
     "keywords": ["world of walker core tee", "walker core tee", "core tee"]},
    {"code": "AW-SHIRT-WWFT", "name": "Walker Washed Fitted Tee", "category": "shirt", "price": 128000.0,
     "keywords": ["walker washed fitted tee", "washed fitted tee", "fitted tee", "1997 tee"]},
    {"code": "AW-SHIRT-EOTW", "name": "End Of The World T-Shirt", "category": "shirt", "price": 464000.0,
     "keywords": ["end of the world t-shirt", "end of the world", "ao end of the world"]},
    {"code": "AW-SHIRT-FGT", "name": "Faded Grafitti T-shirt", "category": "shirt", "price": 596000.0,
     "keywords": ["faded grafitti t-shirt", "faded graffiti t-shirt", "where are you now t-shirt", "grafitti t-shirt"]},
    {"code": "AW-SHIRT-W8BJ", "name": "Walker 8 Baseball Jersey", "category": "shirt", "price": 794000.0,
     "keywords": ["walker 8 baseball jersey", "8 baseball jersey", "baseball 8"]},
    {"code": "AW-SHIRT-W0BJ", "name": "Walker 0 Baseball Jersey", "category": "shirt", "price": 1297000.0,
     "keywords": ["walker 0 baseball jersey", "0 baseball jersey", "baseball 0"]},
    {"code": "AW-SHIRT-TUT", "name": "Tired Unity T-shirt", "category": "shirt", "price": 583000.0,
     "keywords": ["tired unity t-shirt", "tired unity tee"]},
    {"code": "AW-SHIRT-T0T", "name": 'Tired "0" Tee', "category": "shirt", "price": 847000.0,
     "keywords": ["tired 0 tee", "tired 0 t-shirt", 'tired "0" tee']},
    {"code": "AW-SHIRT-WGJ", "name": "Walker Gaming Jersey", "category": "shirt", "price": 662000.0,
     "keywords": ["walker gaming jersey", "gaming jersey", "ao gaming"]},
    {"code": "AW-SHIRT-WOWST", "name": "World of Walker Skyline T-shirt", "category": "shirt", "price": 450000.0,
     "keywords": ["world of walker skyline t-shirt", "skyline t-shirt", "skyline tee"]},
    {"code": "AW-SHIRT-98RJ", "name": "98' Replica Jersey", "category": "shirt", "price": 1165000.0,
     "keywords": ["98 replica jersey", "98' replica jersey", "replica jersey"]},

    # =========================================================================
    # 2. NHÓM HOODIE (Hoodies & Zip Hoodies - 23 mẫu)
    # =========================================================================
    {"code": "AW-HOOD-UPHBK", "name": "Unity Patch Hoodie / Black", "category": "hoodie", "price": 1033000.0,
     "keywords": ["unity patch hoodie black", "unity patch black", "unity patch den"]},
    {"code": "AW-HOOD-UPHBL", "name": "Unity Patch Hoodie / Blue", "category": "hoodie", "price": 1033000.0,
     "keywords": ["unity patch hoodie blue", "unity patch blue", "unity patch xanh", "unity patch hoodie"]},
    {"code": "AW-HOOD-WRLTZ", "name": "WRL Team Zip Hoodie", "category": "hoodie", "price": 1165000.0,
     "keywords": ["wrl team zip hoodie", "wrl zip hoodie", "team zip hoodie"]},
    {"code": "AW-HOOD-WRLSH", "name": "WRL Speed Hoodie", "category": "hoodie", "price": 1165000.0,
     "keywords": ["wrl speed hoodie", "speed hoodie"]},
    {"code": "AW-HOOD-OAW", "name": "The Original AW Hoodie", "category": "hoodie", "price": 768000.0,
     "keywords": ["the original aw hoodie", "original aw hoodie", "original hoodie", "aw hoodie"]},
    {"code": "AW-HOOD-MCKZH", "name": '"Monster" Core Kids Zip Hoodie', "category": "hoodie", "price": 768000.0,
     "keywords": ["monster core kids zip hoodie", "kids zip hoodie", "monster kids hoodie"]},
    {"code": "AW-HOOD-MCH", "name": '"Monster" Core Hoodie', "category": "hoodie", "price": 1165000.0,
     "keywords": ["monster core hoodie", "monster hoodie"]},
    {"code": "AW-HOOD-HHH", "name": "Heading Home Hoodie", "category": "hoodie", "price": 1165000.0,
     "keywords": ["heading home hoodie"]},
    {"code": "AW-HOOD-ATL8", "name": 'Atlantis "8" Hoodie', "category": "hoodie", "price": 1165000.0,
     "keywords": ["atlantis 8 hoodie", 'atlantis "8" hoodie', "atlantis 8"]},
    {"code": "AW-HOOD-ATL0", "name": 'Atlantis "0" Hoodie', "category": "hoodie", "price": 1430000.0,
     "keywords": ["atlantis 0 hoodie", 'atlantis "0" hoodie', "atlantis 0"]},
    {"code": "AW-HOOD-ENCH", "name": "Encyclopedia Hoodie", "category": "hoodie", "price": 1562000.0,
     "keywords": ["encyclopedia hoodie"]},
    {"code": "AW-HOOD-WCH", "name": "Walker Core Hoodie", "category": "hoodie", "price": 264000.0,
     "keywords": ["walker core hoodie", "core hoodie"]},
    {"code": "AW-HOOD-NAH", "name": "NOT ALONE Hoodie", "category": "hoodie", "price": 264000.0,
     "keywords": ["not alone hoodie", "not alone"]},
    {"code": "AW-HOOD-WWLH", "name": "Walkerworld Logo Hoodie", "category": "hoodie", "price": 250000.0,
     "keywords": ["walkerworld logo hoodie", "walkerworld hoodie", "walker world hoodie"]},
    {"code": "AW-HOOD-WTDH", "name": "Watch The Drone Hoodie", "category": "hoodie", "price": 1165000.0,
     "keywords": ["watch the drone hoodie", "watch the drone"]},
    {"code": "AW-HOOD-FGHOW", "name": "Faded Grafitti Hoodie (Off white)", "category": "hoodie", "price": 1165000.0,
     "keywords": ["faded grafitti hoodie off white", "faded graffiti hoodie off white", "grafitti hoodie trang", "grafitti off white"]},
    {"code": "AW-HOOD-FGHBK", "name": "Faded Graffiti Hoodie (Black)", "category": "hoodie", "price": 1165000.0,
     "keywords": ["faded graffiti hoodie black", "faded grafitti hoodie black", "faded graffiti hoodie", "faded grafitti hoodie", "where are you now hoodie"]},
    {"code": "AW-HOOD-PD8H", "name": "Prophecy Disc VIII Hoodie", "category": "hoodie", "price": 1165000.0,
     "keywords": ["prophecy disc viii hoodie", "prophecy disc hoodie", "prophecy hoodie"]},
    {"code": "AW-HOOD-TUH", "name": "Tired Unity Hoodie", "category": "hoodie", "price": 1165000.0,
     "keywords": ["tired unity hoodie"]},
    {"code": "AW-HOOD-T0H", "name": 'Tired "0" Hoodie', "category": "hoodie", "price": 1694000.0,
     "keywords": ["tired 0 hoodie", 'tired "0" hoodie']},
    {"code": "AW-HOOD-WGH", "name": "Walker Gaming Hoodie", "category": "hoodie", "price": 794000.0,
     "keywords": ["walker gaming hoodie", "gaming hoodie"]},
    {"code": "AW-HOOD-WOWSZ", "name": "World of Walker Skyline Zip Hoodie", "category": "hoodie", "price": 927000.0,
     "keywords": ["skyline zip hoodie", "world of walker skyline zip hoodie"]},
    {"code": "AW-HOOD-WOWSH", "name": "World Of Walker Skyline Hoodie", "category": "hoodie", "price": 847000.0,
     "keywords": ["world of walker skyline hoodie", "skyline hoodie"]},

    # =========================================================================
    # 3. NHÓM LONGSLEEVE (Áo dài tay - 4 mẫu)
    # =========================================================================
    {"code": "AW-LS-WRLL", "name": "WRL Logo Longsleeve", "category": "longsleeve", "price": 636000.0,
     "keywords": ["wrl logo longsleeve", "wrl longsleeve"]},
    {"code": "AW-LS-FGL", "name": "Faded Grafitti Longsleeve", "category": "longsleeve", "price": 662000.0,
     "keywords": ["faded grafitti longsleeve", "faded graffiti longsleeve", "grafitti longsleeve"]},
    {"code": "AW-LS-HHL", "name": "Heading Home Longsleeve", "category": "longsleeve", "price": 636000.0,
     "keywords": ["heading home longsleeve"]},
    {"code": "AW-LS-PD8L", "name": "Prophecy Disc VIII Longsleeve", "category": "longsleeve", "price": 662000.0,
     "keywords": ["prophecy disc viii longsleeve", "prophecy longsleeve"]},

    # =========================================================================
    # 4. NHÓM JACKET (Áo khoác Jacket - 3 mẫu)
    # =========================================================================
    {"code": "AW-JKT-CLV1", "name": "Core LV1 Windbreaker", "category": "jacket", "price": 1165000.0,
     "keywords": ["core lv1 windbreaker", "windbreaker", "core lv1", "ao gio"]},
    {"code": "AW-JKT-TLSJ", "name": "The Legendary Sandstone Jacket", "category": "jacket", "price": 5134000.0,
     "keywords": ["the legendary sandstone jacket", "sandstone jacket", "legendary jacket", "red rocks jacket"]},
    {"code": "AW-JKT-AWF1", "name": "Alan Walker F1 Stage Jacket", "category": "jacket", "price": 4341000.0,
     "keywords": ["alan walker f1 stage jacket", "f1 stage jacket", "stage jacket", "f1 jacket"]},
]

# Mẫu đại diện mặc định cho từng phân loại khi khách chỉ nói chung chung (VD: "cho 1 áo hoodie size L")
DEFAULT_MODEL_BY_CATEGORY = {
    "shirt": "AW-SHIRT-SLT",       # Snake Logo Tee (120.000đ)
    "hoodie": "AW-HOOD-WWLH",      # Walkerworld Logo Hoodie (250.000đ)
    "longsleeve": "AW-LS-WRLL",    # WRL Logo Longsleeve (636.000đ)
    "jacket": "AW-JKT-CLV1",       # Core LV1 Windbreaker (1.165.000đ)
}


def build_product_catalog() -> Dict[str, Dict[str, Any]]:
    """
    Sinh toàn bộ 290 mã SKU chuẩn (58 mẫu x 5 size S, M, L, XL, XXL),
    kèm giữ lại các SKU Polo/Jean cũ để tương thích ngược với dữ liệu đã có trong DB.
    """
    catalog: Dict[str, Dict[str, Any]] = {}

    for base in BASE_PRODUCTS:
        for size in SIZES:
            sku = f"{base['code']}-{size}"
            catalog[sku] = {
                "sku": sku,
                "base_code": base["code"],
                "base_name": base["name"],
                "name": f"{base['name']} - Size {size}",
                "price": float(base["price"]),
                "type": base["category"],
                "size": size,
            }

    # Giữ tương thích ngược với các đơn cũ (Polo / Jean từ Giai đoạn 1 & 2)
    legacy_items = {
        "POLO-BLK-S": {"name": "Áo Polo Cotton Đen - Size S", "price": 250000.0, "type": "polo", "size": "S"},
        "POLO-BLK-M": {"name": "Áo Polo Cotton Đen - Size M", "price": 250000.0, "type": "polo", "size": "M"},
        "POLO-BLK-L": {"name": "Áo Polo Cotton Đen - Size L", "price": 250000.0, "type": "polo", "size": "L"},
        "POLO-BLK-XL": {"name": "Áo Polo Cotton Đen - Size XL", "price": 250000.0, "type": "polo", "size": "XL"},
        "POLO-BLK-XXL": {"name": "Áo Polo Cotton Đen - Size XXL", "price": 250000.0, "type": "polo", "size": "XXL"},
        "POLO-WHT-S": {"name": "Áo Polo Cotton Trắng - Size S", "price": 250000.0, "type": "polo", "size": "S"},
        "POLO-WHT-M": {"name": "Áo Polo Cotton Trắng - Size M", "price": 250000.0, "type": "polo", "size": "M"},
        "POLO-WHT-L": {"name": "Áo Polo Cotton Trắng - Size L", "price": 250000.0, "type": "polo", "size": "L"},
        "POLO-WHT-XL": {"name": "Áo Polo Cotton Trắng - Size XL", "price": 250000.0, "type": "polo", "size": "XL"},
        "POLO-WHT-XXL": {"name": "Áo Polo Cotton Trắng - Size XXL", "price": 250000.0, "type": "polo", "size": "XXL"},
        "POLO-NVY-S": {"name": "Áo Polo Cotton Navy - Size S", "price": 250000.0, "type": "polo", "size": "S"},
        "POLO-NVY-M": {"name": "Áo Polo Cotton Navy - Size M", "price": 250000.0, "type": "polo", "size": "M"},
        "POLO-NVY-L": {"name": "Áo Polo Cotton Navy - Size L", "price": 250000.0, "type": "polo", "size": "L"},
        "POLO-NVY-XL": {"name": "Áo Polo Cotton Navy - Size XL", "price": 250000.0, "type": "polo", "size": "XL"},
        "POLO-NVY-XXL": {"name": "Áo Polo Cotton Navy - Size XXL", "price": 250000.0, "type": "polo", "size": "XXL"},
        "JEAN-BLU-30": {"name": "Quần Bò Nam Xanh - Size 30", "price": 350000.0, "type": "jean", "size": "30"},
        "JEAN-BLU-31": {"name": "Quần Bò Nam Xanh - Size 31", "price": 350000.0, "type": "jean", "size": "31"},
        "JEAN-BLU-32": {"name": "Quần Bò Nam Xanh - Size 32", "price": 350000.0, "type": "jean", "size": "32"},
    }
    for sku, meta in legacy_items.items():
        catalog[sku] = {
            "sku": sku,
            "base_code": sku.rsplit("-", 1)[0],
            "base_name": meta["name"].split(" - ")[0],
            **meta,
        }

    return catalog


PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = build_product_catalog()


def get_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Tra cứu thông tin sản phẩm chuẩn từ mã SKU"""
    if not sku:
        return None
    return PRODUCT_CATALOG.get(sku.strip().upper())


def get_catalog_summary() -> Dict[str, Any]:
    """Trả về dữ liệu Catalog chuẩn hóa cho Landing Page và Web Frontend"""
    return {
        "sizes": SIZES,
        "categories": [
            {"id": "shirt", "label": "T-Shirts & Jerseys (28 mẫu)"},
            {"id": "hoodie", "label": "Hoodies & Zip Hoodies (23 mẫu)"},
            {"id": "longsleeve", "label": "Longsleeves - Áo Dài Tay (4 mẫu)"},
            {"id": "jacket", "label": "Jackets - Áo Khoác (3 mẫu)"},
        ],
        "base_products": BASE_PRODUCTS,
        "total_base_products": len(BASE_PRODUCTS),
        "total_skus": len(BASE_PRODUCTS) * len(SIZES),
    }


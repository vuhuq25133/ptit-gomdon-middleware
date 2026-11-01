import os
from typing import Dict, Any, Optional

try:
    import httpx
except ImportError:
    httpx = None

try:
    import requests
except ImportError:
    requests = None

# Cấu hình từ biến môi trường
FB_GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v19.0")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "100234567")

# Kho dữ liệu Mock dự phòng khi chạy offline hoặc test kịch bản
MOCK_FACEBOOK_PROFILES: Dict[str, Dict[str, str]] = {
    "PSID_99887766": {
        "name": "Nguyễn Văn An",
        "avatar": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&h=100&fit=crop&crop=faces"
    },
    "PSID_11223344": {
        "name": "Trần Thu Trang",
        "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=faces"
    },
    "PSID_55667788": {
        "name": "Lê Hoàng Long",
        "avatar": "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=100&h=100&fit=crop&crop=faces"
    }
}

def fetch_facebook_user_profile(psid: str) -> Dict[str, Optional[str]]:
    """
    Lấy thông tin công khai của người dùng nhắn tin qua Facebook Messenger.
    Mô phỏng kiến trúc từ ChatbotX (integrations/messenger/src/apis/user.ts).
    
    Returns:
        dict: {"name": str, "avatar": str, "psid": str}
    """
    # 1. Nếu có token cấu hình thật, gọi Meta Graph API
    if FB_PAGE_ACCESS_TOKEN and not psid.startswith("PSID_MOCK"):
        try:
            url = f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{psid}"
            params = {
                "fields": "first_name,last_name,name,profile_pic",
                "access_token": FB_PAGE_ACCESS_TOKEN
            }
            data = None
            if httpx is not None:
                res = httpx.get(url, params=params, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
            elif requests is not None:
                res = requests.get(url, params=params, timeout=5)
                if res.status_code == 200:
                    data = res.json()

            if data:
                name = data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                return {
                    "name": name or f"Khách FB ({psid[-6:]})",
                    "avatar": data.get("profile_pic") or "",
                    "psid": psid
                }
        except Exception as e:
            print(f"[FacebookService] Gọi Graph API thất bại cho {psid}: {e}")

    # 2. Dự phòng (Fallback / Mock cho môi trường đồ án & kiểm thử)
    if psid in MOCK_FACEBOOK_PROFILES:
        profile = MOCK_FACEBOOK_PROFILES[psid]
        return {
            "name": profile["name"],
            "avatar": profile["avatar"],
            "psid": psid
        }

    # 3. Mặc định sinh tên theo mã PSID
    short_id = psid[-6:] if len(psid) >= 6 else psid
    return {
        "name": f"Khách Facebook ({short_id})",
        "avatar": f"https://api.dicebear.com/7.x/bottts/svg?seed={psid}",
        "psid": psid
    }

def get_meta_business_inbox_url(psid: str, page_id: Optional[str] = None) -> str:
    """
    Tạo đường dẫn mở cuộc trò chuyện trực tiếp trong Meta Business Suite Inbox.
    Mô phỏng từ ChatbotX (integrations/messenger/src/apis/user-inbox-link.ts).
    """
    target_page = page_id or FB_PAGE_ID
    return f"https://business.facebook.com/latest/inbox/messenger?asset_id={target_page}&selected_item_id={psid}"

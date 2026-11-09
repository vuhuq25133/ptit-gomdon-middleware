"""
Facebook Messenger Message & Draft Order Handler
================================================
Xử lý tin nhắn Facebook Messenger (Task 2.4):
1. Bóc tách Regex thông tin (SĐT, địa chỉ, sản phẩm).
2. Nếu CÓ SĐT: Đối chiếu khách hàng, map PSID, sinh hoặc cập nhật ĐƠN NHÁP (status = 'draft').
3. Nếu CHƯA CÓ SĐT: Chỉ lưu câu chat vào hội thoại, TUYỆT ĐỐI KHÔNG sinh khách/đơn.
"""
from app.services.bronze_service import update_bronze_status
from app.services.silver_service import (
    get_or_create_customer,
    create_silver_order,
    link_customer_identity,
    get_customer_id_by_identity,
    get_or_create_conversation,
    save_chat_message,
    get_recent_customer_messages,
    get_existing_draft_order,
    update_silver_draft_order
)
from app.services.chat_extractor import extract_order_from_text
from app.services.facebook_service import fetch_facebook_user_profile


def handle_facebook_message(data: dict):
    """
    Xử lý tin nhắn Facebook Messenger (Task 2.4):
    1. Bóc tách Regex thông tin (SĐT, địa chỉ, sản phẩm, ý định hủy/hỏi giá).
    2. Hỗ trợ hội thoại nhiều tin nhắn (Multi-turn):
       - Nếu khách nhắn sản phẩm trước rồi mới nhắn SĐT ở tin sau -> tổng hợp ngữ cảnh từ hội thoại.
       - Nếu khách đã có đơn nháp (đã định danh PSID) và nhắn bổ sung địa chỉ/sản phẩm ở tin sau -> tự động cập nhật đơn nháp.
    """
    raw_order_id = data["raw_order_id"]
    source_order_id = data["source_order_id"]
    sender_id = data["sender_id"]  # PSID của khách hàng
    page_id = data.get("page_id", "PAGE_DEFAULT")
    text = data.get("text", "")

    print("\n" + "=" * 70)
    print(f"💬 [WORKER FACEBOOK] TIEP NHAN TIN NHAN FB TỪ RABBITMQ")
    print(f"   * PSID:       {sender_id}")
    print(f"   * Fanpage ID: {page_id}")
    print(f"   * Nội dung:   {text}")

    # 1. Gọi module bóc tách tự động Regex (Task 2.3)
    extracted = extract_order_from_text(text)
    print(f"   * Kết quả bóc tách:")
    print(f"     - Ý định:     {extracted.get('intent', 'order')}")
    print(f"     - Có SĐT:     {extracted['has_phone']} ({extracted.get('phone')})")
    print(f"     - Địa chỉ:    {extracted.get('shipping_address')} ({extracted.get('shipping_city')})")
    print(f"     - Sản phẩm:   {len(extracted.get('items', []))} items")
    print(f"     - Độ tin cậy: {extracted.get('confidence_score') * 100:.0f}%")

    customer_id = None

    # Lấy thông tin Nickname & Avatar Facebook (mô phỏng ChatbotX fetchUserProfile)
    fb_profile = fetch_facebook_user_profile(sender_id)
    sender_name = fb_profile.get("name")
    sender_avatar = fb_profile.get("avatar")
    print(f"   [+] Hồ sơ Facebook: {sender_name} | PSID: {sender_id}")

    # NHÁNH 1: Khách CÓ để lại SĐT và KHÔNG phải tin nhắn hủy -> Sinh/Cập nhật ĐƠN NHÁP (status = 'draft')
    if extracted["has_phone"] and extracted.get("intent") != "cancel":
        phone = extracted["phone"]
        default_name = sender_name or f"Khách Facebook ({sender_id[-6:]})"
        address = extracted["shipping_address"] or "Chưa rõ địa chỉ (Cần nhân viên bổ sung)"
        city = extracted["shipping_city"] or "Chưa rõ"

        # 1.1. Đối chiếu SĐT trước ("Một khách - Một hồ sơ")
        customer_id = get_or_create_customer(
            phone=phone,
            full_name=default_name,
            address=address,
            city=city
        )
        print(f"   [+] Đối chiếu khách hàng thành công -> Customer ID #{customer_id}")

        # 1.2. Map định danh Facebook PSID vào customer_identities
        link_customer_identity(
            customer_id=customer_id,
            channel="facebook",
            identity_value=sender_id
        )
        print(f"   [+] Đã map PSID {sender_id} với Customer #{customer_id}")

        # 1.3. Quản lý hội thoại & lưu tin nhắn (kèm Nickname & Avatar Facebook)
        conv_id = get_or_create_conversation(
            channel="facebook",
            channel_conversation_id=sender_id,
            customer_id=customer_id,
            sender_name=sender_name,
            sender_avatar=sender_avatar
        )
        save_chat_message(
            conversation_id=conv_id,
            sender_type="customer",
            content=text,
            has_extracted_order=True,
            external_message_id=source_order_id
        )

        # 1.4. Tổng hợp ngữ cảnh từ các tin nhắn trước trong cùng hội thoại (nếu tin hiện tại chỉ có SĐT)
        items = list(extracted["items"])
        if not items or "Chưa rõ" in address:
            recent_msgs = get_recent_customer_messages(conv_id, limit=6)
            for prev_text in recent_msgs:
                if prev_text == text:
                    continue
                prev_ext = extract_order_from_text(prev_text)
                if prev_ext.get("intent") == "cancel":
                    continue
                if not items and prev_ext.get("items"):
                    items = prev_ext["items"]
                    print(f"   [+] Đã khôi phục {len(items)} sản phẩm từ tin nhắn trước trong hội thoại!")
                if "Chưa rõ" in address and prev_ext.get("shipping_address"):
                    address = prev_ext["shipping_address"]
                    city = prev_ext.get("shipping_city") or city
                    print(f"   [+] Đã khôi phục địa chỉ '{address}' từ tin nhắn trước trong hội thoại!")

        if not items:
            # ⚠️ Không bóc tách được sản phẩm: điền sản phẩm GỢI Ý MẶC ĐỊNH
            # Nhân viên BẮT BUỘC phải kiểm tra và cập nhật trước khi xác nhận đơn
            items = [{
                "sku": "AW-HOOD-WWLH-L",
                "name": "Walkerworld Logo Hoodie - Size L (⚠ Gợi ý mặc định - Cần nhân viên xác nhận)",
                "quantity": 1,
                "price": 250000.0,
                "unit_price": 250000.0
            }]

        total_amount = sum(
            item.get("unit_price", item.get("price", 0.0)) * item.get("quantity", 1) for item in items
        )

        # 1.5. Sinh hoặc Cập nhật ĐƠN NHÁP (status = 'draft')
        existing_draft = get_existing_draft_order(customer_id, channel="facebook")
        if existing_draft:
            order_code = update_silver_draft_order(
                order_id=existing_draft["id"],
                raw_order_id=raw_order_id,
                shipping_name=default_name,
                shipping_phone=phone,
                shipping_address=address,
                shipping_city=city,
                items=items,
                total_amount=total_amount,
                note=f"Đơn nháp cập nhật từ tin nhắn chat mới (Độ tin cậy: {extracted['confidence_score']*100:.0f}%)"
            )
            print(f"   🔄 [CẬP NHẬT ĐƠN NHÁP THÀNH CÔNG] Đã cập nhật vào Đơn ID #{existing_draft['id']} (Mã: {order_code})")
        else:
            order_code = create_silver_order(
                raw_order_id=raw_order_id,
                source_channel="facebook",
                source_order_id=source_order_id,
                customer_id=customer_id,
                shipping_name=default_name,
                shipping_phone=phone,
                shipping_address=address,
                shipping_city=city,
                items=items,
                total_amount=total_amount,
                status="draft",  # ⭐ ĐƠN NHÁP CHO GIAI ĐOẠN 2
                note=f"Đơn nháp sinh tự động từ tin nhắn chat (Độ tin cậy: {extracted['confidence_score']*100:.0f}%)"
            )
            print(f"   🟡 [SINH ĐƠN NHÁP THÀNH CÔNG] Mã đơn: {order_code} (Status: 'draft')")

    # NHÁNH 2: Tin nhắn KHÔNG chứa SĐT (hoặc tin nhắn báo hủy)
    else:
        # Thử tìm xem PSID này đã từng map với customer_id nào trước đây không
        customer_id = get_customer_id_by_identity("facebook", sender_id)

        has_enrichment = bool(
            customer_id
            and extracted.get("intent") != "cancel"
            and (extracted.get("items") or extracted.get("shipping_address"))
        )

        conv_id = get_or_create_conversation(
            channel="facebook",
            channel_conversation_id=sender_id,
            customer_id=customer_id,
            sender_name=sender_name,
            sender_avatar=sender_avatar
        )
        save_chat_message(
            conversation_id=conv_id,
            sender_type="customer",
            content=text,
            has_extracted_order=has_enrichment,
            external_message_id=source_order_id
        )

        # Nếu khách ĐÃ định danh từ tin trước và nhắn bổ sung sản phẩm / địa chỉ -> Bổ sung vào đơn nháp hiện có!
        if has_enrichment:
            existing_draft = get_existing_draft_order(customer_id, channel="facebook")
            if existing_draft:
                new_items = extracted.get("items") or None
                new_addr = extracted.get("shipping_address")
                new_city = extracted.get("shipping_city")
                if new_addr:
                    get_or_create_customer(
                        phone=existing_draft["shipping_phone"],
                        full_name=sender_name or existing_draft["shipping_name"],
                        address=new_addr,
                        city=new_city or existing_draft["shipping_city"]
                    )
                order_code = update_silver_draft_order(
                    order_id=existing_draft["id"],
                    raw_order_id=raw_order_id,
                    shipping_name=sender_name,
                    shipping_phone=existing_draft["shipping_phone"],
                    shipping_address=new_addr,
                    shipping_city=new_city,
                    items=new_items,
                    note=f"Đơn nháp bổ sung thông tin từ hội thoại nhiều tin nhắn"
                )
                print(f"   🔄 [BỔ SUNG ĐƠN NHÁP MULTI-TURN] Đã cập nhật Đơn #{existing_draft['id']} ({order_code}) từ tin nhắn không lặp lại SĐT!")
            else:
                print(f"   [+] Đã lưu tin nhắn vào Conversation #{conv_id} (Khách #{customer_id} chưa có đơn nháp đang mở).")
        else:
            print(f"   ℹ️  Đã lưu tin nhắn vào Conversation #{conv_id} chờ nhân viên tư vấn.")

    # Cập nhật Tầng Bronze -> 'processed'
    update_bronze_status(raw_order_id, "processed")
    print(f"   [+] Đã cập nhật Tầng Bronze (raw_orders #{raw_order_id}) -> 'processed'")
    print("=" * 70 + "\n")

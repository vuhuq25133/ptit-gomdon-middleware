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
    get_existing_draft_order,
    update_silver_draft_order
)
from app.services.chat_extractor import extract_order_from_text
from app.services.facebook_service import fetch_facebook_user_profile


def handle_facebook_message(data: dict):
    """
    Xử lý tin nhắn Facebook Messenger (Task 2.4):
    1. Bóc tách Regex thông tin (SĐT, địa chỉ, sản phẩm).
    2. Nếu CÓ SĐT: Đối chiếu khách hàng, map PSID, sinh ĐƠN NHÁP (status = 'draft').
    3. Nếu CHƯA CÓ SĐT: Chỉ lưu câu chat vào hội thoại, TUYỆT ĐỐI KHÔNG sinh khách/đơn.
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

    # NHÁNH 1: Khách CÓ để lại SĐT -> Sinh ĐƠN NHÁP (status = 'draft')
    if extracted["has_phone"]:
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
            has_extracted_order=True
        )

        # 1.4. Sinh ĐƠN NHÁP (orders với status = 'draft')
        items = extracted["items"]
        if not items:
            # ⚠️ Không bóc tách được sản phẩm: điền sản phẩm GỢI Ý MẶC ĐỊNH
            # Nhân viên BẮT BUỘC phải kiểm tra và cập nhật trước khi xác nhận đơn
            items = [{
                "sku": "POLO-BLK-L",
                "name": "Áo Polo Cotton Đen - Size L (⚠ Gợi ý mặc định - Cần nhân viên xác nhận)",
                "quantity": 1,
                "price": 250000.0,
                "unit_price": 250000.0
            }]

        total_amount = extracted.get("total_amount") or sum(
            item.get("unit_price", item.get("price", 0.0)) * item.get("quantity", 1) for item in items
        )

        # 1.4. Sinh hoặc Cập nhật ĐƠN NHÁP (status = 'draft')
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

    # NHÁNH 2: Khách CHƯA để lại SĐT -> Chỉ lưu hội thoại, TUYỆT ĐỐI KHÔNG TẠO customer / order
    else:
        print(f"   ℹ️  Khách chưa để lại SĐT -> Không tạo hồ sơ khách / đơn hàng.")
        # Thử tìm xem PSID này đã từng map với customer_id nào trước đây không
        customer_id = get_customer_id_by_identity("facebook", sender_id)

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
            has_extracted_order=False
        )
        print(f"   [+] Đã lưu tin nhắn vào Conversation #{conv_id} chờ nhân viên tư vấn.")

    # Cập nhật Tầng Bronze -> 'processed'
    update_bronze_status(raw_order_id, "processed")
    print(f"   [+] Đã cập nhật Tầng Bronze (raw_orders #{raw_order_id}) -> 'processed'")
    print("=" * 70 + "\n")

"""Transactional, page-scoped conversation drafts and extraction evidence."""
import re
import uuid
from copy import deepcopy
from psycopg2.extras import Json
from app.core.database import get_db
from app.services.chat_extractor import extract_order_from_text


FIELDS = ('phone', 'shipping_address', 'shipping_city', 'items')


def extract_patch(text):
    result = extract_order_from_text(text)
    issues = []
    # The legacy extractor defaults missing/unsupported variants. Accept only
    # explicitly specified quantities, sizes and colors for Messenger drafts.
    product = bool(re.search(r'\b(?:áo|polo|quần|jean|size|sz)\b', text, re.I))
    if product:
        quantities = re.findall(r'(\d+)\s*(?:áo|quần|cái|chiếc|bộ|đôi)\b', text, re.I)
        sizes = re.findall(r'\b(?:size|sz)\s*(xxl|2xl|xl|s|m|l|\d+)\b', text, re.I)
        colors = [code for code, pattern in (
            ('BLK', r'\b(?:đen|black)\b'), ('WHT', r'\b(?:trắng|white)\b'),
            ('NVY', r'\b(?:navy|xanh than)\b'), ('BLU', r'\bxanh\b')
        ) if re.search(pattern, text, re.I)]
        if 'NVY' in colors and 'BLU' in colors:
            colors.remove('BLU')
        items = result['items']
        valid = (len(quantities) == len(sizes) == len(colors) == len(items) == 1
                 and int(quantities[0]) > 0 and '?' not in text)
        if valid:
            valid = items[0]['sku'].endswith('-' + sizes[0].upper()) and (
                '-' + colors[0] + '-') in items[0]['sku']
        if not valid:
            result['items'] = []
            issues.append('Sản phẩm/số lượng/màu/size chưa rõ hoặc không hỗ trợ; cần nhân viên xác nhận')
    else:
        result['items'] = []
    return result, issues


def merge_draft(state, patch, evidence, issues):
    """Missing fields never erase known values; conflicts retain both sources."""
    state = deepcopy(state or {'fields': {}, 'evidence': {}, 'issues': []})
    for field in FIELDS:
        value = patch.get(field)
        if not value:
            continue
        event = dict(evidence, value=value)
        history = state['evidence'].setdefault(field, [])
        if event not in history:
            history.append(event)
        previous = state['fields'].get(field)
        if previous and previous != value:
            issue = {'field': field, 'reason': 'conflict', 'proposal': event}
            if issue not in state['issues']:
                state['issues'].append(issue)
        else:
            state['fields'][field] = value
    for reason in issues:
        issue = {'field': 'items', 'reason': reason, 'proposal': evidence}
        if issue not in state['issues']:
            state['issues'].append(issue)
    state['needs_review'] = True  # Messenger never auto-confirms a purchase.
    state['missing_fields'] = [key for key in FIELDS if not state['fields'].get(key)]
    return state


def process_message(data, profile):
    page = data.get('page_id') or 'PAGE_DEFAULT'
    sender = data['sender_id']
    key = f'{page}:{sender}'
    text = data.get('text', '')
    patch, issues = extract_patch(text)
    with get_db() as cur:
        # Serialize all workers handling this conversation, even its first event.
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (key,))
        cur.execute("SELECT id FROM conversations WHERE channel='facebook' AND channel_conversation_id=%s", (key,))
        row = cur.fetchone()
        if row:
            conversation_id = row['id']
        else:
            cur.execute("""INSERT INTO conversations(channel, channel_conversation_id, sender_name, sender_avatar)
                           VALUES ('facebook', %s, %s, %s) RETURNING id""",
                        (key, profile.get('name'), profile.get('avatar')))
            conversation_id = cur.fetchone()['id']
        cur.execute('SELECT id FROM messages WHERE raw_order_id=%s', (data['raw_order_id'],))
        if cur.fetchone():
            return  # Entire previous attempt committed, including Bronze status.
        cur.execute("""INSERT INTO messages(conversation_id, sender_type, content, has_extracted_order, raw_order_id)
                       VALUES (%s, 'customer', %s, %s, %s) RETURNING id""",
                    (conversation_id, text, any(patch.get(f) for f in FIELDS), data['raw_order_id']))
        message_id = cur.fetchone()['id']
        cur.execute('SELECT state, order_id FROM conversation_drafts WHERE conversation_id=%s FOR UPDATE', (conversation_id,))
        draft = cur.fetchone()
        state = draft['state'] if draft else None
        order_id = draft['order_id'] if draft else None
        if order_id:
            cur.execute('SELECT status FROM orders WHERE id=%s FOR UPDATE', (order_id,))
            if cur.fetchone()['status'] != 'draft':
                # A completed order must never supply products/address to a new purchase.
                state, order_id = None, None
        evidence = {'message_id': message_id, 'raw_order_id': data['raw_order_id'],
                    'source_order_id': data['source_order_id'], 'text': text}
        state = merge_draft(state, patch, evidence, issues)
        fields = state['fields']
        cur.execute("""SELECT c.id, c.phone FROM customer_identities i JOIN customers c ON c.id=i.customer_id
                       WHERE i.channel='facebook' AND i.identity_value=%s""", (key,))
        customer = cur.fetchone()
        if not customer:
            # Compatibility with identities stored by the previous PSID-only handler.
            cur.execute("""SELECT c.id, c.phone FROM customer_identities i JOIN customers c ON c.id=i.customer_id
                           WHERE i.channel='facebook' AND i.identity_value=%s""", (sender,))
            customer = cur.fetchone()
        # A changed phone is a proposal, never an automatic identity reassignment.
        if customer and fields.get('phone') and fields['phone'] != customer['phone']:
            state['issues'].append({'field': 'phone', 'reason': 'identity_conflict', 'proposal': evidence})
            state['evidence'].setdefault('phone', []).append({'customer_id': customer['id'], 'value': customer['phone'], 'source': 'customer_identity'})
            fields['phone'] = customer['phone']
        if customer and not fields.get('phone'):
            fields['phone'] = customer['phone']
            state['evidence'].setdefault('phone', []).append({'customer_id': customer['id'], 'value': customer['phone'], 'source': 'customer_identity'})
        elif not customer and fields.get('phone'):
            cur.execute("""INSERT INTO customers(phone, full_name) VALUES (%s,%s)
                           ON CONFLICT(phone) DO UPDATE SET phone=EXCLUDED.phone RETURNING id, phone""",
                        (fields['phone'], profile.get('name') or sender))
            customer = cur.fetchone()
            cur.execute("""INSERT INTO customer_identities(customer_id, channel, identity_value)
                           VALUES (%s,'facebook',%s)""", (customer['id'], key))
        if customer:
            cur.execute('UPDATE conversations SET customer_id=%s WHERE id=%s', (customer['id'], conversation_id))
        state['missing_fields'] = [f for f in FIELDS if not fields.get(f)]
        # Partial drafts live independently of customers. Only project actual items
        # into Silver; never manufacture a default product for phone-only messages.
        if customer and fields.get('items'):
            items = fields['items']
            total = sum(i['quantity'] * i['unit_price'] for i in items)
            note = 'Cần nhân viên xác nhận. ' + str({'missing': state['missing_fields'], 'issues': state['issues']})
            values = (profile.get('name') or sender, fields['phone'], fields.get('shipping_address', ''),
                      fields.get('shipping_city', ''), total, note)
            if not order_id:
                cur.execute("""INSERT INTO orders(order_code, source_channel, source_order_id, customer_id,
                               shipping_name, shipping_phone, shipping_address, shipping_city, total_amount, note, status, raw_order_id)
                               VALUES (%s,'facebook',%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s) RETURNING id""",
                            ('ORD_FB_' + uuid.uuid4().hex[:16], data['source_order_id'], customer['id'], *values, data['raw_order_id']))
                order_id = cur.fetchone()['id']
            else:
                cur.execute("""UPDATE orders SET shipping_name=%s, shipping_phone=%s, shipping_address=%s,
                               shipping_city=%s, total_amount=%s, note=%s, updated_at=NOW() WHERE id=%s AND status='draft'""",
                            (*values, order_id))
            cur.execute('DELETE FROM order_items WHERE order_id=%s', (order_id,))
            for item in items:
                cur.execute('INSERT INTO order_items(order_id,sku,product_name,quantity,price) VALUES (%s,%s,%s,%s,%s)',
                            (order_id, item['sku'], item['name'], item['quantity'], item['unit_price']))
        cur.execute("""INSERT INTO conversation_drafts(conversation_id,state,order_id) VALUES (%s,%s,%s)
                       ON CONFLICT(conversation_id) DO UPDATE SET state=EXCLUDED.state, order_id=EXCLUDED.order_id, updated_at=NOW()""",
                    (conversation_id, Json(state), order_id))
        cur.execute("UPDATE raw_orders SET process_status='processed', error_message=NULL WHERE id=%s", (data['raw_order_id'],))

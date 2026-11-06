import unittest
from app.services.facebook_draft_service import extract_patch, merge_draft


class DraftTests(unittest.TestCase):
    def apply(self, state, text, mid):
        patch, issues = extract_patch(text)
        return merge_draft(state, patch, {'message_id': mid, 'text': text}, issues)

    def test_three_messages_preserve_purchase_and_provenance(self):
        state = None
        for mid, text in enumerate(['Cho mình 2 áo trắng size M.', 'Số điện thoại 0905111222.', 'Giao 45 Lê Duẩn, Đà Nẵng.'], 1):
            state = self.apply(state, text, mid)
        self.assertEqual(state['fields']['items'][0]['sku'], 'POLO-WHT-M')
        self.assertEqual(state['fields']['items'][0]['quantity'], 2)
        self.assertEqual(state['fields']['phone'], '0905111222')
        self.assertEqual(state['fields']['shipping_address'], '45 Lê Duẩn, Đà Nẵng')
        self.assertEqual(state['missing_fields'], [])
        self.assertEqual(state['evidence']['items'][0]['message_id'], 1)
        self.assertEqual(state['evidence']['phone'][0]['message_id'], 2)
        self.assertEqual(state['evidence']['shipping_address'][0]['message_id'], 3)
        self.assertTrue(state['needs_review'])

    def test_phone_only_never_invents_items(self):
        state = self.apply(None, '0905111222', 1)
        self.assertNotIn('items', state['fields'])

    def test_conflict_keeps_original_and_proposal(self):
        state = self.apply(None, 'Giao 45 Lê Duẩn, Đà Nẵng.', 1)
        changed = self.apply(state, 'Giao 99 Lê Duẩn, Đà Nẵng.', 2)
        self.assertEqual(changed['fields']['shipping_address'], state['fields']['shipping_address'])
        self.assertEqual(changed['issues'][0]['proposal']['message_id'], 2)
        self.assertEqual(len(changed['evidence']['shipping_address']), 2)

    def test_ambiguous_or_unsupported_product_requires_review(self):
        for text in ['Cho mình 2 áo.', 'Cho mình 2 áo trắng size XXL.',
                     'Cho mình 2 áo trắng size M và 3 áo đen size L.',
                     '2 áo trắng size M giá bao nhiêu?']:
            with self.subTest(text=text):
                patch, issues = extract_patch(text)
                self.assertFalse(patch['items'])
                self.assertTrue(issues)

    def test_unrelated_message_keeps_fields(self):
        state = self.apply(None, 'Cho mình 2 áo trắng size M.', 1)
        newer = self.apply(state, 'Cảm ơn shop', 2)
        self.assertEqual(newer['fields'], state['fields'])


if __name__ == '__main__':
    unittest.main()

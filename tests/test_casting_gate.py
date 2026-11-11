import json
import tempfile
import unittest
from unittest.mock import patch
from test_pagecast import ROOT
from pagecast_test.books import Books

class CastingGateTests(unittest.TestCase):
    def test_uncast_roles_are_visible_and_block_before_voice_planning_or_speech(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            books=Books(tmp);identifier=books.import_book(text='A test passage.')['book_id']
            (books.folder(identifier)/'render-block.json').write_text(json.dumps({'reason':'Two voices need casting','pending_count':2}))
            self.assertEqual(books.overview(identifier)['render_block']['pending_count'],2)
            with patch.object(books,'plan') as plan, self.assertRaisesRegex(ValueError,'Two voices need casting'):
                books.render(identifier)
            plan.assert_not_called()
            self.assertEqual(books.usage(identifier)['requests'],0)

if __name__=='__main__':unittest.main()

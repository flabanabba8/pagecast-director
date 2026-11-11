import json
import tempfile
import unittest
from unittest.mock import patch
from test_pagecast import ROOT
from pagecast_test.books import Books


class SpoilerTests(unittest.TestCase):
    def test_safe_overview_receipts_and_deliberate_identity_disclosure(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp)
            identifier = books.import_book(text='An unknown visitor arrived.\nThe visitor was Mira.\nShe opened a window.')['book_id']
            books.set_voice(identifier,'Narrator',engine='inworld')
            assigned = books.assign(identifier,[0,1,2],'Mira')
            role = assigned['speaker']
            self.assertTrue(role.startswith('role_'));self.assertNotIn('Mira',json.dumps(assigned))
            note = books.cast_note(identifier,role,'Mira','Private future relationship and plot notes',reveal_after=1)
            self.assertNotIn('Mira',json.dumps(note))
            books.set_voice(identifier,role,engine='inworld',voice='Ashley',inworld_options={'reasoningContext':'Private future relationship and plot notes'},replace_locked=True)
            safe = books.overview(identifier)
            serialized = json.dumps(safe)
            for hidden in ['Mira','unknown visitor','Private future','reasoningContext','performance']:
                self.assertNotIn(hidden,serialized)
            self.assertNotIn('passages',safe)
            context = books.direction_context(identifier)
            self.assertEqual(context['private_casting_notes'][0]['identity'],'Mira')
            self.assertIn('SPOILER-SAFE DEFAULT',context['instructions'])
            books.reading_position(identifier,0)
            self.assertNotIn('Mira',json.dumps(books.overview(identifier)))
            books.reading_position(identifier,1)
            self.assertEqual(books.overview(identifier)['voices'][role]['label'],'Mira')
            books.reading_position(identifier,-1)
            with patch.object(books,'_export',return_value={}), patch('pagecast_test.readalong.package',side_effect=lambda book,passages,audio:passages):
                rows = books.readalong(identifier)
            self.assertNotEqual(rows[0]['speaker'],'Mira');self.assertNotEqual(rows[1]['speaker'],'Mira')
            self.assertEqual(rows[2]['speaker'],'Mira')
            self.assertNotIn('notes',rows[0])

    def test_legacy_names_are_masked_and_resolve_back_to_locked_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Books(tmp);identifier=b.import_book(text='A line.')['book_id']
            with b.db() as db:
                db.execute('INSERT INTO voices VALUES(?,?,?,1)',(identifier,'Future villain',json.dumps({'engine':'inworld','voice':'Ashley'})))
                db.execute('UPDATE passages SET speaker=? WHERE book=?',('Future villain',identifier))
            result=b.get(identifier)
            self.assertNotIn('Future villain',json.dumps(result))
            role=result['passages'][0]['speaker']
            with self.assertRaisesRegex(ValueError,'locked'):b.set_voice(identifier,role,engine='inworld',voice='Dennis')

if __name__=='__main__':unittest.main()

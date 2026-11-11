import json
import tempfile
import unittest
from test_pagecast import ROOT
from pagecast_test.books import Books


class SeriesTests(unittest.TestCase):
    def test_two_books_reuse_identity_alias_voice_model_direction_and_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Books(tmp);series=b.series_create('Synthetic series')['id']
            self.assertEqual(b.series_create('synthetic SERIES')['id'],series)
            narrator=b.series_voice(series,'Narrator',voice='Dennis',inworld_options={'timestampType':'WORD'},direction='clear natural storytelling')
            role=b.series_voice(series,'Mina',voice='Ashley',aliases=['Min'],notes='Private character notes',inworld_options={'timestampType':'WORD'},direction='bright clear speech')
            ids=[b.import_book(text='“An original line.”')['book_id'] for _ in range(2)]
            for identifier in ids:
                b.series_link(identifier,series)
                self.assertEqual(b.get(identifier)['voices']['Narrator']['voice'],'Dennis')
            first=b.assign(ids[0],[0],'Mina');second=b.assign(ids[1],[0],'Min')
            self.assertEqual(first['speaker'],role['role']);self.assertEqual(second['speaker'],role['role'])
            for identifier in ids:
                plan=b.plan(identifier);voice=plan[2][role['role']]
                self.assertEqual(voice['voice'],'Ashley');self.assertEqual(voice['model'],'inworld-tts-2')
                self.assertEqual(plan[1][0]['speech_text'],'[bright clear speech] “An original line.”')
                self.assertTrue(b.get(identifier)['voices'][role['role']]['locked'])
                with self.assertRaisesRegex(ValueError,'series cast'):
                    b.set_voice(identifier,role['role'],engine='inworld',voice='Dennis',replace_locked=True)
            changed_default=Books(tmp,{'inworld_model':'inworld-tts-2-flash'})
            self.assertEqual(changed_default.plan(ids[1])[2][role['role']]['model'],'inworld-tts-2')
            public=json.dumps(b.series_list())+json.dumps(b.overview(ids[0]))
            for hidden in ['Mina','Min"','Private character']:self.assertNotIn(hidden,public)
            private=b.direction_context(ids[0]);self.assertTrue(private['private_series_cast'])

    def test_explicit_global_replacement_updates_linked_books_and_preserves_unrelated_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Books(tmp);series=b.series_create('A series')['id']
            role=b.series_voice(series,'Mina',voice='Ashley')
            ids=[b.import_book(text='One.\nTwo.')['book_id'] for _ in range(2)]
            before=[]
            for identifier in ids:
                b.series_link(identifier,series);b.assign(identifier,[0],'Mina')
                b.set_voice(identifier,'Narrator',engine='inworld',voice='Dennis')
                before.append(b.plan(identifier)[1])
            with self.assertRaisesRegex(ValueError,'locked'):b.series_voice(series,'Mina',voice='Sarah')
            result=b.series_voice(series,'Mina',voice='Sarah',replace_locked=True)
            self.assertEqual(result['updated_books'],2)
            for identifier,old in zip(ids,before):
                after=b.plan(identifier)[1]
                self.assertNotEqual(old[0]['signature'],after[0]['signature'])
                self.assertEqual(old[1]['signature'],after[1]['signature'])
                self.assertEqual(b.get(identifier)['voices'][role['role']]['voice'],'Sarah')

    def test_failed_link_rolls_back_and_alias_collisions_do_not_change_cast(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Books(tmp);series=b.series_create('A series')['id']
            b.series_voice(series,'Narrator',voice='Dennis')
            b.series_voice(series,'Mina',voice='Ashley',aliases=['Min'])
            with self.assertRaisesRegex(ValueError,'alias'):b.series_voice(series,'Another person',voice='Sarah',aliases=['MIN'])
            identifier=b.import_book(text='Hello.')['book_id']
            b.set_voice(identifier,'Narrator',engine='inworld',voice='Ashley',locked=True)
            with self.assertRaisesRegex(ValueError,'locked'):b.series_link(identifier,series)
            self.assertNotIn('series',b.get(identifier)['book'])
            self.assertEqual(b.get(identifier)['voices']['Narrator']['voice'],'Ashley')

if __name__=='__main__':unittest.main()

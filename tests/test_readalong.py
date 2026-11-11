import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from test_pagecast import ROOT
from test_inworld import Connection
from pagecast_test import inworld
from pagecast_test.books import Books
from pagecast_test.readalong import word_spans


class ReadalongTests(unittest.TestCase):
    def test_controls_validate_before_network_and_map_native_fields(self):
        controls = {'speakingRate': .9, 'timestampType': 'WORD', 'deliveryMode': 'CREATIVE', 'reasoning': True,
                    'reasoningContext': 'Quiet library.', 'previousTexts': ['Hello.'], 'language': 'en-US', 'lipsync': True}
        Connection.calls = []; Connection.status = 200; Connection.invalid_audio = False
        with patch.object(inworld, 'credential', return_value='fixture'), patch.object(inworld, 'InworldConnection', Connection):
            inworld.synthesize('[whisper] Hello.', 'Ashley', controls=controls)
        body = Connection.calls[-1]['payload']
        self.assertEqual(body['synthesisContext'], {'reasoning': 'REASONING_ON', 'reasoningContext': 'Quiet library.', 'previousRequests': [{'text': 'Hello.'}]})
        self.assertEqual(body['audioConfig']['speakingRate'], .9)
        self.assertEqual(body['timestampType'], 'WORD')
        for bad in ({'temperature': 1}, {'speakingRate': float('nan')}, {'language': 8}, {'previousTexts': ['x'*2001]}, {'reasoning': 'yes'}, {'secret': 'no'}):
            with patch.object(inworld, 'request') as request:
                with self.assertRaises(ValueError): inworld.synthesize('Hello.', 'Ashley', controls=bad)
                request.assert_not_called()
        with self.assertRaises(ValueError): inworld.options({'reasoning': True}, 'inworld-tts-2-flash')

    def test_direction_is_revision_checked_preserves_source_and_selective_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            books=Books(tmp); identifier=books.import_book(text='Hello there.\nAnother line.')['book_id']
            books.set_voice(identifier, 'Narrator', engine='inworld')
            before=books.plan(identifier)[1]; context=books.direction_context(identifier)
            revision=context['book']['revision']
            self.assertIn('currently running this harness', context['instructions'])
            books.direct(identifier, revision, [{'passage_id': 0, 'text': '[say quietly] Hello <break time="500ms" />there. [reset]'}])
            after=books.plan(identifier)[1]
            self.assertNotEqual(before[0]['signature'], after[0]['signature'])
            self.assertEqual(before[1]['signature'], after[1]['signature'])
            self.assertEqual(books.get(identifier)['source_text_status'], 'unchanged')
            with self.assertRaisesRegex(ValueError, 'Stale'): books.direct(identifier, revision, [{'passage_id':0,'text':'Hello there.'}])
            revision=books.get(identifier)['book']['revision']
            with self.assertRaisesRegex(ValueError, 'preserve'): books.direct(identifier, revision, [{'passage_id':0,'text':'Rewritten.'}])
            books.edit(identifier, 0, 'A changed line.')
            self.assertEqual(books.plan(identifier)[1][0]['speech_text'], 'A changed line.')

    def test_ipa_and_saved_dictionary_controls(self):
        self.assertEqual(inworld.performance_text('[say Crete softly] Welcome to Crete.', {'Crete': '/kriːt/'}), '[say Crete softly] Welcome to /kriːt/.')
        with self.assertRaises(ValueError): inworld.performance_text('Crete', {'Crete': '/two words/'})
        settings = {'language': 'en-US', 'pronunciationDictionarySettings': {'dictionaries': [{'dictionary': 'workspaces/WORKSPACE/pronunciationDictionaries/DICTIONARY'}]}}
        self.assertEqual(inworld.options(settings), settings)
        with self.assertRaises(ValueError): inworld.options({**settings, 'enableCustomPronunciation': False})

    def test_word_alignment_fallback_and_utf16_offsets(self):
        def metadata(words, starts, ends): return {'timestamp_info': {'wordAlignment': {'words': words, 'wordStartTimeSeconds': starts, 'wordEndTimeSeconds': ends}}}
        self.assertEqual(word_spans('😀 hello', metadata(['😀','hello'], [0,.2], [.1,.4]), 1)[1]['from'], 3)
        self.assertEqual(word_spans('12 cats', metadata(['twelve','cats'], [0,.2], [.1,.4]), 1), [])
        self.assertEqual(word_spans('hello', metadata(['hello'], [float('nan')], [.4]), 1), [])

    def test_real_inworld_alignment_shape_skips_silent_tags_and_empty_tokens(self):
        metadata = {'timestamp_info': {'wordAlignment': {
            'words': ['[warm narration]', ' ', 'Hello', ' ', 'there', '.', ''],
            'wordStartTimeSeconds': [0,0,0,.2,.2,.7,.9],
            'wordEndTimeSeconds': [0,0,.2,.2,.7,.9,1]}}}
        spans = word_spans('Hello there.', metadata, 1)
        self.assertEqual([(s['from'],s['to']) for s in spans], [(0,5),(6,11),(11,12)])
        self.assertEqual(spans[1]['start'], .2)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_readalong_export_no_paid_requests_reuses_cache_and_escapes_script(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(inworld,'credential',return_value='fixture'), patch.object(inworld,'InworldConnection',Connection):
            Connection.calls=[];Connection.status=200;Connection.invalid_audio=False
            books=Books(tmp); identifier=books.import_book(title='</script><script>bad</script>',text='Hello there.')['book_id']
            books.set_voice(identifier,'Narrator',engine='inworld',inworld_options={'timestampType':'WORD'})
            self.assertEqual(books.render(identifier)['state'],'complete')
            calls=len(Connection.calls)
            receipt=books.export(identifier,'readalong')
            self.assertEqual(len(Connection.calls),calls)
            with zipfile.ZipFile(receipt['path']) as archive:
                self.assertEqual(set(archive.namelist()), {'reader.html','audiobook.m4b','book.json','READ-ME.txt'})
                manifest=json.loads(archive.read('book.json'))
                self.assertEqual(manifest['passages'][0]['text'],'Hello there.')
                self.assertNotIn(b'</script><script>bad',archive.read('reader.html'))
                self.assertNotIn(tmp.encode(),archive.read('book.json'))
            self.assertEqual(books.render(identifier)['generated'],0)
            self.assertEqual(len(Connection.calls),calls)

if __name__=='__main__':unittest.main()

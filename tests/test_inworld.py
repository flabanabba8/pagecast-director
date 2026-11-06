import base64
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
import os
from unittest.mock import patch

from test_pagecast import ROOT
from pagecast_test import inworld
from pagecast_test.books import Books, verify_cache


def wav():
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
        audio.writeframes(b'\0\0' * 9600)
    return out.getvalue()


class Connection:
    calls = []
    status = 200
    invalid_audio = False
    def __init__(self, host, timeout): self.host = host; self.path = ''; self.payload = None
    def connect(self): pass
    def request(self, method, path, body=None, headers=None):
        self.path, self.payload = path, json.loads(body) if body else None
        self.calls.append({'host': self.host, 'method': method, 'path': path, 'payload': self.payload, 'headers': headers})
    def getresponse(self): return self
    def read(self, _):
        if self.path.startswith('/voices/'):
            return json.dumps({'voices': [{'voiceId': 'Ashley', 'displayName': 'Ashley', 'languageCode': 'en-US'}], 'nextPageToken': 'next-page'}).encode()
        return json.dumps({'audioContent': 'not base64!' if self.invalid_audio else base64.b64encode(wav()).decode(),
                           'usage': {'processedCharactersCount': 12, 'modelId': 'inworld-tts-2'}}).encode()
    def close(self): pass


class InworldTests(unittest.TestCase):
    def setUp(self): Connection.calls = []; Connection.status = 200; Connection.invalid_audio = False

    def test_native_api_auth_audio_and_reported_usage(self):
        events = []
        with patch.object(inworld, 'credential', return_value='Zml4dHVyZTpmaXh0dXJl'), patch.object(inworld.http.client, 'HTTPSConnection', Connection):
            audio, usage = inworld.synthesize('Hello there.', 'Ashley', observe=lambda *event: events.append(event))
        call = Connection.calls[0]
        self.assertEqual(call['host'], 'api.inworld.ai')
        self.assertEqual(call['path'], '/tts/v1/voice')
        self.assertEqual(call['headers']['Authorization'], 'Basic Zml4dHVyZTpmaXh0dXJl')
        self.assertEqual(call['payload']['modelId'], 'inworld-tts-2')
        self.assertEqual(call['payload']['audioConfig'], {'audioEncoding': 'LINEAR16', 'sampleRateHertz': 48000})
        self.assertTrue(audio.startswith(b'RIFF')); self.assertEqual(usage['reported_units'], 12)
        self.assertEqual([e[0] for e in events], ['pending', 'received'])

    def test_higgs_reference_cannot_read_private_credential_directory(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp)
            private = root/'.codex'
            private.mkdir()
            reference = private/'fixture.wav'
            reference.write_bytes(wav())
            books = Books(root/'books')
            book = books.import_book(text='Original sample.')
            with self.assertRaisesRegex(ValueError, 'Private configuration'):
                books.set_voice(book['book_id'], 'Narrator', engine='higgs', reference_audio=str(reference))

    def test_utf16_limit_before_credentials_or_network(self):
        with patch.object(inworld, 'credential') as key:
            with self.assertRaises(ValueError): inworld.synthesize('😀' * 1001, 'Ashley')
            key.assert_not_called()

    def test_redirect_is_not_followed_and_error_does_not_leak_key(self):
        Connection.status = 302
        with patch.object(inworld, 'credential', return_value='Zml4dHVyZTpmaXh0dXJl'), patch.object(inworld.http.client, 'HTTPSConnection', Connection):
            with self.assertRaises(inworld.InworldError) as error: inworld.synthesize('Hello.', 'Ashley')
        self.assertEqual(len(Connection.calls), 1)
        self.assertNotIn('Zml4dHVyZTpmaXh0dXJl', str(error.exception))

    def test_voice_catalog_and_custom_pagination(self):
        with patch.object(inworld, 'credential', return_value='fixture'), patch.object(inworld.http.client, 'HTTPSConnection', Connection):
            result = inworld.voices()
        self.assertEqual(result['voices'][0]['id'], 'Ashley')
        self.assertEqual(result['next_page_token'], 'next-page')
        self.assertIn('source%3D%22SYSTEM%22', Connection.calls[0]['path'])

    def test_denied_voice_catalog_offers_manual_voice_id(self):
        Connection.status = 403
        with patch.object(inworld, 'credential', return_value='fixture'), patch.object(inworld.http.client, 'HTTPSConnection', Connection):
            with self.assertRaisesRegex(inworld.InworldError, 'enter a known voice ID'):
                inworld.voices()
        self.assertEqual(len(Connection.calls), 1)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_book_cache_and_paid_retry_guard(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(inworld, 'credential', return_value='Zml4dHVyZTpmaXh0dXJl'), patch.object(inworld.http.client, 'HTTPSConnection', Connection):
            books = Books(tmp); identifier = books.import_book(text='Hello there.')['book_id']
            books.set_voice(identifier, 'Narrator', engine='inworld')
            Connection.invalid_audio = True
            self.assertEqual(books.render(identifier)['state'], 'failed')
            self.assertEqual(books.usage(identifier)['reported_characters'], 12)
            self.assertEqual(books.render(identifier)['state'], 'failed')
            self.assertEqual(len(Connection.calls), 1, 'Must not repeat a possibly billed failed request')
            books.retry(identifier, [0]); Connection.invalid_audio = False
            self.assertEqual(books.render(identifier)['state'], 'complete')
            self.assertEqual(len(Connection.calls), 2)
            self.assertEqual(books.render(identifier)['generated'], 0)
            self.assertEqual(len(Connection.calls), 2, 'Cache replay must make no synthesis request')
            cache = Path(books.plan(identifier)[1][0]['audio_path']).parent
            cache.rename(cache.parent / '.staging-interrupted')
            recovered = books.render(identifier)
            self.assertEqual(recovered['recovered'], 1)
            self.assertEqual(recovered['generated'], 0)
            self.assertEqual(len(Connection.calls), 2, 'Complete staged audio must be recovered without another paid call')
            self.assertEqual(books.usage(identifier)['reported_characters'], 24)
            verify_cache(books.plan(identifier)[1][0]['audio_path'])
            for file in Path(tmp).rglob('*'):
                if file.is_file(): self.assertNotIn(b'Zml4dHVyZTpmaXh0dXJl', file.read_bytes(), str(file))

    def test_new_speakers_inherit_selected_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); identifier = books.import_book(text='“An original line.”')['book_id']
            books.set_voice(identifier, 'Narrator', engine='inworld', voice='Ashley')
            books.assign(identifier, [0], 'Mina')
            self.assertEqual(books.get(identifier)['voices']['Mina']['engine'], 'inworld')
            with patch('pagecast_test.books.shutil.which', return_value=None):
                books.plan(identifier)  # Inworld-only books do not require Flite
            second = books.import_book(text='A new original line.')['book_id']
            books.assign(second, [0], 'Only speaker')
            books.set_voice(second, 'Only speaker', engine='inworld')
            with patch('pagecast_test.books.shutil.which', return_value=None):
                books.plan(second)  # an unused default Flite narrator is not a dependency

    def test_media_helpers_do_not_inherit_cloud_credentials(self):
        from pagecast_test.process_env import process_env
        with patch.dict(os.environ, {'INWORLD_API_KEY': 'fixture', 'OPENAI_API_KEY': 'fixture', 'DISPLAY': ':17'}):
            env = process_env()
        self.assertNotIn('INWORLD_API_KEY', env)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertEqual(env['DISPLAY'], ':17')


if __name__ == '__main__': unittest.main()

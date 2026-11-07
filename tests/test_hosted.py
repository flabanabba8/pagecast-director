import base64
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_pagecast import ROOT  # noqa: F401  (loads the package under test)
from test_inworld import wav
from pagecast_test import hosted
from pagecast_test.books import Books


class Connection:
    calls = []
    status = 200
    mode = 'ok'
    def __init__(self, host, timeout): self.host = host
    def connect(self): pass
    def request(self, method, path, body=None, headers=None):
        self.path = path
        self.calls.append({'host': self.host, 'method': method, 'path': path, 'payload': json.loads(body), 'headers': headers})
    def getresponse(self): return self
    def read(self, _):
        if self.host == 'api.elevenlabs.io':
            return b'\0\0' * (9600 if self.mode == 'ok' else 1)
        data = base64.b64encode(wav() if self.mode == 'ok' else b'junk').decode()
        return json.dumps({'steps': [{'type': 'model_output', 'content': [{'type': 'audio', 'data': data}]}]}).encode()
    def close(self): pass


def patched(name, key):
    return patch.object(hosted, 'secret', return_value=key), patch.object(hosted.http.client, 'HTTPSConnection', Connection)


class HostedTests(unittest.TestCase):
    def setUp(self): Connection.calls = []; Connection.status = 200; Connection.mode = 'ok'

    def test_elevenlabs_request_shape_and_wav_wrap(self):
        a, b = patched('x', 'fixture-key')
        with a, b:
            audio, usage = hosted.elevenlabs('Hello there.', 'Rachel')
        call = Connection.calls[0]
        self.assertEqual((call['host'], call['method']), ('api.elevenlabs.io', 'POST'))
        self.assertEqual(call['path'], '/v1/text-to-speech/Rachel?output_format=pcm_24000')
        self.assertEqual(call['headers']['xi-api-key'], 'fixture-key')
        self.assertEqual(call['payload'], {'text': 'Hello there.', 'model_id': 'eleven_multilingual_v2'})
        self.assertTrue(audio.startswith(b'RIFF')); self.assertEqual(usage['model_id'], 'eleven_multilingual_v2')

    def test_gemini_request_shape_and_audio_extraction(self):
        a, b = patched('x', 'fixture-key')
        with a, b:
            audio, _ = hosted.gemini('Hello there.', 'Kore')
        call = Connection.calls[0]
        self.assertEqual((call['host'], call['path']), ('generativelanguage.googleapis.com', '/v1beta/interactions'))
        self.assertEqual(call['headers']['x-goog-api-key'], 'fixture-key')
        self.assertEqual(call['payload']['generation_config'], {'speech_config': [{'voice': 'Kore'}]})
        self.assertEqual(call['payload']['response_format']['type'], 'audio')
        self.assertTrue(audio.startswith(b'RIFF'))

    def test_invalid_audio_is_reported_without_retry_or_key_leak(self):
        Connection.mode = 'bad'
        for fn, voice in ((hosted.elevenlabs, 'Rachel'), (hosted.gemini, 'Kore')):
            Connection.calls = []
            a, b = patched('x', 'fixture-key')
            with a, b, self.assertRaises(hosted.HostedError) as error:
                fn('Hello.', voice)
            self.assertEqual(len(Connection.calls), 1); self.assertNotIn('fixture-key', str(error.exception))

    def test_http_error_not_retried_and_limits_checked_before_credentials(self):
        Connection.status = 429
        a, b = patched('x', 'fixture-key')
        with a, b, self.assertRaisesRegex(hosted.HostedError, 'quota'):
            hosted.gemini('Hello.', 'Kore')
        self.assertEqual(len(Connection.calls), 1)
        with patch.object(hosted, 'secret') as key:
            with self.assertRaises(ValueError): hosted.elevenlabs('😀' * 1001, 'Rachel')
            with self.assertRaises(ValueError): hosted.gemini('Hi', '../x')
            key.assert_not_called()

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_books_render_and_cache_with_each_engine(self):
        for engine, voice in (('elevenlabs', 'Rachel'), ('gemini', 'Kore')):
            Connection.calls = []
            a, b = patched('x', 'fixture-key')
            with tempfile.TemporaryDirectory() as tmp, a, b:
                books = Books(tmp); identifier = books.import_book(text='Hello there.')['book_id']
                books.set_voice(identifier, 'Narrator', engine=engine, voice=voice)
                self.assertEqual(books.render(identifier)['state'], 'complete')
                self.assertEqual(books.render(identifier)['generated'], 0)
                self.assertEqual(len(Connection.calls), 1)
                self.assertEqual(books.usage(identifier)['requests'], 1)

    def test_set_voice_rejects_unknown_engine_and_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); identifier = books.import_book(text='Hello there.')['book_id']
            with self.assertRaises(ValueError): books.set_voice(identifier, 'Narrator', engine='nope')
            with self.assertRaises(ValueError): books.set_voice(identifier, 'Narrator', engine='gemini', voice='Kore', reference_text='x')


if __name__ == '__main__':
    unittest.main()

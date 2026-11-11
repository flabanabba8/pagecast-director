import base64
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from test_pagecast import ROOT
from test_inworld import wav
from pagecast_test import vertex
from pagecast_test.books import Books


class Client:
    def __init__(self):
        self.headers = {}; self.calls = []; self.status = 200; self.fail = False
    def head(self, *args, **kwargs): return Mock(status_code=404)
    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.fail: raise OSError('fixture network error')
        return Mock(status_code=self.status, content=b'fixture', json=lambda: {
            'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 50},
            'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
                {'inlineData': {'mimeType': 'audio/wav', 'data': base64.b64encode(wav()).decode()}}]}}]})


class VertexTests(unittest.TestCase):
    def test_native_render_verbatim_vertex_request_usage_cache_and_budget(self):
        client = Client()
        @contextmanager
        def session(): yield client
        with tempfile.TemporaryDirectory() as tmp, patch.object(vertex, 'session', session), patch.object(vertex, 'signed_post', lambda url, body, project, timeout=240.0, _c=client: _c.post(url, headers={'x-goog-user-project': project}, json=body, allow_redirects=False)):
            books = Books(tmp, {'gemini_route': 'vertex', 'gemini_project': 'fixture-project', 'gemini_max_usd': 3})
            identifier = books.import_book(text='Hello there.')['book_id']
            books.set_voice(identifier, 'Narrator', engine='inworld', voice='Ashley')
            revision = books.get(identifier)['book']['revision']
            books.direct(identifier, revision, [{'passage_id': 0, 'text': '[Speak eagerly] Hello there.'}])
            books.set_voice(identifier, 'Narrator', engine='gemini', voice='fixture_voice', replace_locked=True)
            result = books.render(identifier)
            self.assertEqual(result['state'], 'complete', result)
            url, kwargs = client.calls[0]
            self.assertIn('/v1/projects/fixture-project/locations/global/', url)
            self.assertTrue(url.endswith('gemini-3.8-flash-tts:generateContent'))
            self.assertEqual(kwargs['json']['contents'], [{'role': 'user', 'parts': [{'text': 'Hello there.'}]}])
            self.assertEqual(kwargs['json']['generationConfig']['speechConfig']['voiceConfig'], {'voice': 'fixture_voice'})
            self.assertFalse(kwargs['allow_redirects'])
            self.assertEqual(books.render(identifier)['generated'], 0)
            self.assertEqual(len(client.calls), 1)
            ledger_path = books.folder(identifier) / 'vertex-usage.json'
            ledger = json.loads(ledger_path.read_text())
            self.assertEqual(ledger[0]['output_tokens'], 50)
            self.assertEqual(books.usage(identifier)['unknown_outcomes'], 0)
            self.assertEqual(books.usage(identifier)['vertex']['input_tokens'], 12)
            self.assertEqual(books.usage(identifier)['vertex']['output_tokens'], 50)
            self.assertAlmostEqual(ledger[0]['reserved_or_actual_usd'], .000912)
            ledger_path.write_text(json.dumps([{'reserved_or_actual_usd': 3}]))
            with self.assertRaisesRegex(vertex.HostedError, 'spending guard'):
                vertex.synthesize('Hello.', 'fixture_voice', 'gemini-3.8-flash-tts', None, project='fixture-project', ledger_path=ledger_path)
            self.assertEqual(len(client.calls), 1)

    def test_reservation_scales_with_text_and_guard_stays_strict(self):
        client = Client()
        @contextmanager
        def session(): yield client
        short = 'Storms never care about tea, lass. ' * 20
        self.assertLess(vertex.estimate_usd(short), 0.10)
        self.assertEqual(vertex.estimate_usd('Hi.'), vertex.MIN_RESERVATION)
        self.assertEqual(vertex.estimate_usd('x' * 100000), vertex.RESERVATION)
        with tempfile.TemporaryDirectory() as tmp, patch.object(vertex, 'session', session), patch.object(vertex, 'signed_post', lambda url, body, project, timeout=240.0, _c=client: _c.post(url, headers={'x-goog-user-project': project}, json=body, allow_redirects=False)):
            ledger_path = Path(tmp) / 'u.json'
            audio, _ = vertex.synthesize(short, 'fixture_voice', 'gemini-3.8-flash-tts', None, project='fixture-project', ledger_path=ledger_path, max_usd=0.10)
            self.assertTrue(audio)
            self.assertAlmostEqual(json.loads(ledger_path.read_text())[0]['reserved_or_actual_usd'], .000912)
            with self.assertRaises(vertex.HostedError) as raised:
                vertex.synthesize('x' * 2000, 'fixture_voice', 'gemini-3.8-flash-tts', None, project='fixture-project', ledger_path=ledger_path, max_usd=0.10)
            message = str(raised.exception)
            self.assertIn('no speech request sent', message)
            self.assertIn('0.1 USD', message); self.assertIn('gemini_max_usd', message)
            self.assertEqual(len(client.calls), 1)
            ledger_path.write_text(json.dumps([{'reserved_or_actual_usd': 0.098}]))
            with self.assertRaisesRegex(vertex.HostedError, 'spending guard'):
                vertex.synthesize(short, 'fixture_voice', 'gemini-3.8-flash-tts', None, project='fixture-project', ledger_path=ledger_path, max_usd=0.10)

    def test_uncertain_post_reserves_cost_and_is_not_automatically_repeated(self):
        client = Client(); client.fail = True
        @contextmanager
        def session(): yield client
        with tempfile.TemporaryDirectory() as tmp, patch.object(vertex, 'session', session), patch.object(vertex, 'signed_post', lambda url, body, project, timeout=240.0, _c=client: _c.post(url, headers={'x-goog-user-project': project}, json=body, allow_redirects=False)):
            books = Books(tmp, {'gemini_route': 'vertex', 'gemini_project': 'fixture-project'})
            identifier = books.import_book(text='Hello there.')['book_id']
            books.set_voice(identifier, 'Narrator', engine='gemini', voice='fixture_voice')
            self.assertEqual(books.render(identifier)['state'], 'failed')
            self.assertEqual(books.render(identifier)['state'], 'failed')
            self.assertEqual(len(client.calls), 1)
            ledger = json.loads((books.folder(identifier) / 'vertex-usage.json').read_text())
            self.assertEqual(ledger[0]['status'], 'unknown')
            self.assertEqual(books.usage(identifier)['unknown_outcomes'], 1)
            self.assertEqual(books.usage(identifier)['vertex']['unknown_requests'], 1)
            self.assertEqual(ledger[0]['reserved_or_actual_usd'], vertex.estimate_usd('Hello there.'))


    def test_unreadable_ledger_does_not_expose_contents_or_reset_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); identifier = books.import_book(text='Hello.')['book_id']
            ledger = books.folder(identifier) / 'vertex-usage.json'
            original = '{"private": "fixture-private-value"}'
            ledger.write_text(original)
            result = books.usage(identifier)
            self.assertEqual(result['vertex'], {'available': False})
            self.assertNotIn('fixture-private-value', json.dumps(result))
            self.assertEqual(ledger.read_text(), original)


if __name__ == '__main__': unittest.main()


class HermesSignInTests(unittest.TestCase):
    """The plugin holds no Google credential: Hermes signs the request and no other tool's login is read."""
    def test_not_signed_in_sends_nothing_and_keeps_no_ledger_row(self):
        def refuse(*a, **k): raise vertex.NotSent('Not signed in to Google through Hermes; no speech POST sent. ' + vertex.SETUP)
        with tempfile.TemporaryDirectory() as tmp, patch.object(vertex, 'signed_post', refuse):
            from pathlib import Path
            ledger = Path(tmp) / 'vertex-usage.json'
            with self.assertRaisesRegex(vertex.HostedError, 'hermes auth add pagecast-director:google'):
                vertex.synthesize('Hello.', 'Kore', 'gemini-3.8-flash-tts', None, project='fixture-project', ledger_path=ledger)
            self.assertEqual(json.loads(ledger.read_text()), [])

    def test_outside_hermes_the_request_is_refused_before_sending(self):
        with self.assertRaises(vertex.NotSent):
            vertex.signed_post('https://aiplatform.googleapis.com/v1/x', {}, 'fixture-project')

    def test_source_reads_no_other_tools_login(self):
        from pathlib import Path
        code = '\n'.join(l for l in Path(vertex.__file__).read_text().split('"""', 2)[2].splitlines())
        for banned in ('google.auth', 'subprocess', 'application_default', '.refresh(', 'Bearer', 'import requests'):
            self.assertNotIn(banned, code, banned)


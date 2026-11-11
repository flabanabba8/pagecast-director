"""Each tool the live test did not call is called once through the registered entry point."""
from contextlib import contextmanager
import json
import tempfile
import unittest
from unittest.mock import patch, Mock

from test_pagecast import package, ROOT
from test_vertex import Client
from pagecast_test import vertex

TEXT = 'The lamp swung low.\n"Storms never care about tea," said Bram.\n"Then drink it fast," said Marta.'
SETTINGS = {'gemini_route': 'vertex', 'gemini_project': 'fixture-project', 'gemini_max_usd': 0.10}


class ToolSmokeTests(unittest.TestCase):
    def test_every_previously_untested_tool_runs_once(self):
        client = Client()
        @contextmanager
        def session(): yield client
        with tempfile.TemporaryDirectory() as tmp, patch.object(vertex, 'session', session), \
                patch.object(vertex, 'signed_post', lambda url, body, project, timeout=240.0, _c=client: _c.post(url, headers={'x-goog-user-project': project}, json=body, allow_redirects=False)):
            def call(name, **args):
                result = json.loads(package.invoke(name, args, SETTINGS, tmp))
                self.assertFalse(result.get('error'), (name, result))
                return result
            book = call('pagecast_import', title='Lamp', text=TEXT)['book_id']
            series = call('pagecast_series_create', title='Lamp series')
            series_id = series.get('id') or series.get('series_id') or series['series']['id']
            self.assertTrue(call('pagecast_series_list')['series'])
            call('pagecast_series_link', book_id=book, series_id=series_id)
            call('pagecast_series_voice', series_id=series_id, identity='Bram', engine='gemini', voice='fixture_voice')
            context = call('pagecast_direction_context', book_id=book)
            self.assertIn('passages', context)
            call('pagecast_reading_position', book_id=book, passage_id=0)
            speaker = next(p['speaker'] for p in call('pagecast_book', book_id=book)['passages'])
            call('pagecast_cast_note', book_id=book, speaker=speaker, identity='Keeper', notes='private', reveal_after=1)
            call('pagecast_voice', book_id=book, speaker=speaker, engine='inworld', voice='Ashley')
            call('pagecast_assign', book_id=book, passage_ids=[1], speaker=speaker)
            revision = call('pagecast_book', book_id=book)['book']['revision']
            call('pagecast_direct', book_id=book, expected_revision=revision, changes=[{'passage_id': 0, 'text': 'The lamp swung low.'}])
            call('pagecast_voice', book_id=book, speaker=speaker, engine='gemini', voice='fixture_voice', replace_locked=True)
            self.assertEqual(call('pagecast_render', book_id=book)['state'], 'complete')
            call('pagecast_cancel', book_id=book)
            self.assertTrue(call('pagecast_timeline', book_id=book))
            usage = call('pagecast_usage', book_id=book)
            self.assertGreaterEqual(usage['vertex']['received'], 1)
            requests = len(client.calls)
            call('pagecast_retry', book_id=book, passage_ids=[0])
            with patch('shutil.which', return_value=None):
                preview = json.loads(package.invoke('pagecast_preview', {'book_id': book, 'passage_id': 0}, SETTINGS, tmp))
            self.assertIsInstance(preview, dict)
            self.assertEqual(len(client.calls), requests)

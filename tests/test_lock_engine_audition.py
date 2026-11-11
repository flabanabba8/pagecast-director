"""0.3.4: locked voices need human approval, speech engine honesty, Gemini audition, silent previews."""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch, Mock

from test_pagecast import package, ROOT
from test_vertex import Client
from test_inworld import wav
from pagecast_test import vertex, voice_audition
from pagecast_test.books import Books

GEMINI = {'gemini_route': 'vertex', 'gemini_project': 'fixture-project', 'gemini_max_usd': 1}


def call(name, args, tmp, settings=None, source='hermes'):
    return json.loads(package.invoke(name, args, settings or {}, tmp, source=source))


def fixture(tmp, text='Hello there.\n"Hi," said Mira.'):
    books = Books(tmp, GEMINI)
    book = books.import_book(text=text)['book_id']
    return books, book


class LockApprovalTests(unittest.TestCase):
    def test_voice_override_is_asked_with_names_and_kept_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            books.set_voice(book, 'Narrator', engine='gemini', voice='Leda')  # locked by default
            ask = package.on_pre_tool_call('pagecast_voice', {'book_id': book, 'speaker': 'Narrator', 'engine': 'gemini', 'voice': 'Kore', 'replace_locked': True}, GEMINI, tmp)
            self.assertEqual(ask['action'], 'approve')
            for part in ('Narrator', 'locked voice gemini voice Leda', 'would become gemini voice Kore'): self.assertIn(part, ask['message'])
            # nothing changes -> no question, and the tool says so
            same = {'book_id': book, 'speaker': 'Narrator', 'engine': 'gemini', 'voice': 'Leda', 'replace_locked': True}
            self.assertIsNone(package.on_pre_tool_call('pagecast_voice', same, GEMINI, tmp))
            self.assertIn('lock kept', call('pagecast_voice', same, tmp, GEMINI)['lock'])
            # no replace_locked flag -> no approval (the tool refuses a locked change itself, in plain words)
            plain = {k: v for k, v in same.items() if k != 'replace_locked'} | {'voice': 'Kore'}
            self.assertIsNone(package.on_pre_tool_call('pagecast_voice', plain, GEMINI, tmp))
            self.assertIn('was left as it is', call('pagecast_voice', plain, tmp, GEMINI)['error'])

    def test_connection_without_approval_never_overrides_but_hermes_and_ui_paths_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            books.set_voice(book, 'Narrator', engine='gemini', voice='Leda')
            args = {'book_id': book, 'speaker': 'Narrator', 'engine': 'gemini', 'voice': 'Kore', 'replace_locked': True}
            refused = call('pagecast_voice', args, tmp, GEMINI, source='mcp')
            self.assertIn('needs the user to approve', refused['error'])
            self.assertEqual(books.get(book)['voices']['Narrator']['voice'], 'Leda')
            self.assertEqual(call('pagecast_voice', args, tmp, GEMINI, source='hermes')['voice']['voice'], 'Kore')  # the hook asked first
            args['voice'] = 'Aoede'
            self.assertEqual(call('pagecast_voice', args, tmp, GEMINI, source='ui')['voice']['voice'], 'Aoede')  # a person in the editor

    def test_unevaluable_override_still_asks(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            odd = {'book_id': book, 'speaker': 'Narrator', 'engine': 'bogus', 'replace_locked': True}
            ask = package.on_pre_tool_call('pagecast_voice', odd, {}, tmp)
            self.assertEqual(ask['action'], 'approve')
            self.assertIn('could not be checked', ask['message'])
            self.assertIn('needs the user to approve', call('pagecast_voice', odd, tmp, source='mcp')['error'])

    def test_series_link_and_series_voice_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            series = books.series_create('Harbor')['id']
            books.series_voice(series, 'Narrator', engine='gemini', voice='Kore')
            # the book narrator is locked on a different voice than the series cast
            books.set_voice(book, 'Narrator', engine='gemini', voice='Leda')
            link = {'book_id': book, 'series_id': series, 'replace_locked': True}
            ask = package.on_pre_tool_call('pagecast_series_link', link, GEMINI, tmp)
            self.assertEqual(ask['action'], 'approve')
            for part in ('Narrator', 'gemini voice Leda', 'gemini voice Kore'): self.assertIn(part, ask['message'])
            self.assertIn('needs the user to approve', call('pagecast_series_link', link, tmp, GEMINI, source='mcp')['error'])
            self.assertIn('was left as it is'[:0] or 'locked', call('pagecast_series_link', {k: v for k, v in link.items() if k != 'replace_locked'}, tmp, GEMINI)['error'])
            self.assertEqual(books.get(book)['voices']['Narrator']['voice'], 'Leda')
            self.assertEqual(call('pagecast_series_link', link, tmp, GEMINI)['inherited_voices'], 1)
            # now it matches: no question, lock kept
            self.assertIsNone(package.on_pre_tool_call('pagecast_series_link', link, GEMINI, tmp))
            self.assertIn('lock kept', call('pagecast_series_link', link, tmp, GEMINI)['lock'])
            # series voice replacement
            sv = {'series_id': series, 'identity': 'Narrator', 'engine': 'gemini', 'voice': 'Aoede', 'replace_locked': True}
            ask = package.on_pre_tool_call('pagecast_series_voice', sv, GEMINI, tmp)
            self.assertEqual(ask['action'], 'approve')
            for part in ('Narrator', 'gemini voice Kore', 'gemini voice Aoede'): self.assertIn(part, ask['message'])
            self.assertIn('needs the user to approve', call('pagecast_series_voice', sv, tmp, GEMINI, source='mcp')['error'])
            unchanged = {**sv, 'voice': 'Kore'}
            self.assertIsNone(package.on_pre_tool_call('pagecast_series_voice', unchanged, GEMINI, tmp))
            self.assertIn('lock kept', call('pagecast_series_voice', unchanged, tmp, GEMINI)['lock'])
            self.assertEqual(call('pagecast_series_voice', sv, tmp, GEMINI)['role'], 'Narrator')

    def test_hook_is_registered_with_settings(self):
        class Context:
            def __init__(self): self.hooks = {}
            def get_config(self, key): return None
            def register_hook(self, name, fn): self.hooks[name] = fn
            def register_tool(self, **kwargs): pass
        ctx = Context(); package.register(ctx)
        self.assertEqual(ctx.hooks['pre_tool_call'](tool_name='pagecast_preview', args={'book_id': 'x', 'passage_id': 0, 'play': True})['action'], 'approve')
        self.assertIsNone(ctx.hooks['pre_tool_call'](tool_name='pagecast_preview', args={'book_id': 'x', 'passage_id': 0}))


class EngineHonestyTests(unittest.TestCase):
    def render_book(self, tmp, client):
        books, book = fixture(tmp)
        books.set_voice(book, 'Narrator', engine='gemini', voice='Kore')
        return books, book

    def patches(self, client):
        @contextmanager
        def session(): yield client
        return patch.object(vertex, 'session', session), patch.object(vertex, 'credentials', return_value=Mock(valid=True, token='fixture-token'))

    def test_render_states_engine_voice_and_billing_and_cached_reuse(self):
        client = Client(); a, b = self.patches(client)
        with tempfile.TemporaryDirectory() as tmp, a, b:
            books, book = self.render_book(tmp, client)
            first = call('pagecast_render', {'book_id': book}, tmp, GEMINI)
            self.assertEqual(first['state'], 'complete')
            row = first['speech_used'][0]
            self.assertEqual((row['engine'], row['voice'], row['billed']), ('gemini', 'Kore', 'yes'))
            self.assertEqual(first['billed_this_call'], 'yes'); self.assertIn('BILLED', first['speech_summary']); self.assertIn('gemini voice Kore', first['speech_summary'])
            again = call('pagecast_render', {'book_id': book}, tmp, GEMINI)
            self.assertEqual(again['billed_this_call'], 'no'); self.assertEqual(again['speech_used'][0]['passages_generated'], 0)
            self.assertEqual(len(client.calls), first['generated'])

    @unittest.skipUnless(shutil.which('flite'), 'needs flite')
    def test_local_flite_is_labelled_local_and_never_called_gemini(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp, 'One short line.')
            result = call('pagecast_render', {'book_id': book}, tmp, GEMINI)
            self.assertEqual(result['state'], 'complete')
            self.assertEqual((result['speech_used'][0]['engine'], result['speech_used'][0]['billed']), ('flite', 'no'))
            self.assertIn('not billed', result['speech_summary'])

    def test_requested_engine_or_voice_that_the_cast_does_not_match_is_refused_without_fallback(self):
        client = Client(); a, b = self.patches(client)
        with tempfile.TemporaryDirectory() as tmp, a, b:
            books, book = fixture(tmp)  # Narrator is cast as local Flite by default
            refused = call('pagecast_render', {'book_id': book, 'engine': 'gemini', 'voice': 'Leda'}, tmp, GEMINI)
            self.assertIn('Narrator is cast as flite voice rms', refused['error']); self.assertIn('no other engine was substituted', refused['error']); self.assertIn('Options', refused['error'])
            self.assertEqual(client.calls, [])
            books.set_voice(book, 'Narrator', engine='gemini', voice='Kore')
            wrong_voice = call('pagecast_render', {'book_id': book, 'engine': 'gemini', 'voice': 'Leda'}, tmp, GEMINI)
            self.assertIn('gemini voice Kore', wrong_voice['error']); self.assertEqual(client.calls, [])
            ok = call('pagecast_render', {'book_id': book, 'engine': 'gemini', 'voice': 'Kore'}, tmp, GEMINI)
            self.assertEqual(ok['state'], 'complete'); self.assertTrue(client.calls)
            self.assertIn('Name the engine', call('pagecast_render', {'book_id': book, 'voice': 'Kore'}, tmp, GEMINI)['error'])

    def test_unavailable_local_engine_is_refused_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp, patch('shutil.which', return_value=None):
            books, book = fixture(tmp, 'One line.')
            result = call('pagecast_render', {'book_id': book}, tmp, GEMINI)
            self.assertIn('Install Flite', result['error'] if 'error' in result else '')


class PreviewTests(unittest.TestCase):
    def rendered(self, tmp):
        client = Client()
        @contextmanager
        def session(): yield client
        books, book = fixture(tmp, 'One line.')
        books.set_voice(book, 'Narrator', engine='gemini', voice='Kore')
        with patch.object(vertex, 'session', session), patch.object(vertex, 'credentials', return_value=Mock(valid=True, token='t')):
            result = books.render(book); self.assertEqual(result['state'], 'complete', result)
        return books, book

    def test_default_preview_plays_nothing_and_names_the_file_and_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = self.rendered(tmp)
            popen_patch = patch('subprocess.Popen'); popen = popen_patch.start(); self.addCleanup(popen_patch.stop)
            result = call('pagecast_preview', {'book_id': book, 'passage_id': 0}, tmp, GEMINI)
            popen.assert_not_called()
            self.assertIs(result['played'], False); self.assertEqual(result['state'], 'ready')
            self.assertTrue(Path(result['file']).is_file()); self.assertEqual((result['engine'], result['voice']), ('gemini', 'Kore'))
            self.assertIn('no -', result['billed'])
            self.assertIs(call('pagecast_preview', {'book_id': book, 'passage_id': 0, 'play': False}, tmp, GEMINI, source='mcp')['played'], False)
            popen.assert_not_called()

    def test_play_is_explicit_asks_approval_and_is_refused_on_connections_that_cannot_ask(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = self.rendered(tmp)
            for target, kw in (('subprocess.Popen', {}), ('shutil.which', {'return_value': '/usr/bin/mpv'})):
                started = patch(target, **kw).start(); self.addCleanup(patch.stopall)
                if target == 'subprocess.Popen': popen = started
            args = {'book_id': book, 'passage_id': 0, 'play': True}
            self.assertEqual(package.on_pre_tool_call('pagecast_preview', args)['action'], 'approve')
            self.assertIsNone(package.on_pre_tool_call('pagecast_preview', {**args, 'play': False}))
            self.assertIn('cannot ask the user', call('pagecast_preview', args, tmp, GEMINI, source='mcp')['error'])
            popen.assert_not_called()
            self.assertIs(call('pagecast_preview', args, tmp, GEMINI)['played'], True); self.assertEqual(popen.call_count, 1)
            # a person pressing Preview in the editor (no play argument) still hears it
            self.assertIs(call('pagecast_preview', {'book_id': book, 'passage_id': 0}, tmp, GEMINI, source='ui')['played'], True); self.assertEqual(popen.call_count, 2)


class GeminiAuditionTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        @contextmanager
        def session(): yield self.client
        self.patches = [patch.object(vertex, 'session', session), patch.object(vertex, 'credentials', return_value=Mock(valid=True, token='t')), patch.object(voice_audition, 'PAUSE_SECONDS', 0)]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in self.patches: p.stop()

    def test_vertex_route_one_line_per_voice_listed_and_book_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            before = (books.get(book)['book']['revision'], books.get(book)['voices'])
            result = call('pagecast_voice_audition', {'book_id': book, 'speaker': 'Mira', 'voices': ['Leda', 'Kore']}, tmp, GEMINI)
            self.assertEqual([(r['engine'], r['voice']) for r in result['candidates']], [('gemini', 'Leda'), ('gemini', 'Kore')])
            for r in result['candidates']:
                self.assertGreater(r['seconds'], 0); self.assertAlmostEqual(r['cost_usd_estimate'], .000912, places=5); self.assertEqual(r['billed'], 'yes'); self.assertTrue(Path(r['path']).is_file())
            self.assertEqual(result['billed'], 'yes'); self.assertIn('BILLED', result['speech_summary']); self.assertIsNone(result['stopped'])
            self.assertEqual([c[1]['json']['generationConfig']['speechConfig']['voiceConfig']['voice'] for c in self.client.calls], ['Leda', 'Kore'])
            self.assertEqual((books.get(book)['book']['revision'], books.get(book)['voices']), before)  # nothing added, nothing locked
            ledger = json.loads((books.folder(book) / 'vertex-usage.json').read_text()); self.assertEqual(len(ledger), 2)  # same ledger as rendering

    def test_spend_guard_unknown_voice_and_missing_route_refuse_before_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            args = {'book_id': book, 'speaker': 'Mira', 'voices': ['Leda', 'Kore']}
            self.assertIn('Spending guard', call('pagecast_voice_audition', args, tmp, {**GEMINI, 'gemini_max_usd': 0.005})['error'])
            unknown = call('pagecast_voice_audition', {**args, 'voices': ['Leda', 'Nobody']}, tmp, GEMINI)['error']
            self.assertIn('Nobody', unknown); self.assertIn('Options:', unknown)
            self.assertIn('Gemini is not configured', call('pagecast_voice_audition', args, tmp, {})['error'])
            self.assertIn('2 to 6', call('pagecast_voice_audition', {**args, 'voices': ['Leda']}, tmp, GEMINI)['error'])
            self.assertIn('Options', call('pagecast_voice_audition', {'book_id': book, 'speaker': 'Mira', 'engine': 'gemini'}, tmp, GEMINI)['error'])
            self.assertEqual(self.client.calls, [])
            ledger = books.folder(book) / 'vertex-usage.json'; ledger.write_text(json.dumps([{'reserved_or_actual_usd': 0.999}]))
            self.assertIn('Spending guard', call('pagecast_voice_audition', args, tmp, GEMINI)['error']); self.assertEqual(self.client.calls, [])

    def test_failure_stops_without_retry_and_reports_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            self.client.status = 429
            result = call('pagecast_voice_audition', {'book_id': book, 'speaker': 'Mira', 'voices': ['Leda', 'Kore']}, tmp, GEMINI)
            self.assertEqual(result['candidates'], []); self.assertEqual(result['stopped']['voice'], 'Leda'); self.assertEqual(len(self.client.calls), 1)
            self.assertEqual(result['billed'], 'unknown')

    def test_developer_route_uses_mocked_transport(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(voice_audition.hosted, 'gemini', return_value=(wav(), {})) as hosted_call:
            books, book = fixture(tmp)
            result = call('pagecast_voice_audition', {'book_id': book, 'speaker': 'Mira', 'voices': ['Leda', 'Kore']}, tmp, {'gemini_route': 'developer', 'gemini_max_usd': 1})
            self.assertEqual(hosted_call.call_count, 2); self.assertEqual([r['route'] for r in result['candidates']], ['developer'] * 2)
            self.assertIn('upper estimate', result['candidates'][0]['cost_basis'])

    def test_higgs_path_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            books, book = fixture(tmp)
            self.assertIn('voices applies to engine gemini only', call('pagecast_voice_audition', {'book_id': book, 'speaker': 'Mira', 'engine': 'higgs', 'voices': ['Leda', 'Kore']}, tmp)['error'])
            self.assertIn('Audition supports', call('pagecast_voice_audition', {'book_id': book, 'speaker': 'Mira', 'engine': 'flite'}, tmp)['error'])


if __name__ == '__main__': unittest.main()

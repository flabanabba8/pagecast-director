"""PageCast builds its speech route from what this computer has, and interviews the user first."""
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from test_pagecast import package, ROOT
from pagecast_test import speech_resources as sr
from pagecast_test.books import Books

ANSWERS = {'needs': 'an audiobook of a short story', 'quality': 'plain-ok', 'allow_cloud': False, 'allow_paid': False, 'budget_usd': 0, 'has': [], 'voice_notes': ''}
HAVE_FLITE = bool(shutil.which('flite'))


def call(name, args, tmp, settings=None, source='hermes'):
    return json.loads(package.invoke(name, args, settings or {}, tmp, source=source))


def tools(*names):
    return lambda *a, **k: {n: '/bin/' + n for n in names}


class FirstUse(unittest.TestCase):
    def test_render_and_chosen_cast_ask_which_voice_first_and_pick_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sr, 'system_tools', tools('flite', 'espeak-ng')):
            book = Books(tmp).import_book(text='Hello there.')['book_id']
            out = call('pagecast_render', {'book_id': book}, tmp)
            self.assertEqual(out['state'], 'interview_needed'); self.assertGreaterEqual(len(out['questions']), 6)
            self.assertEqual({o['id'] for o in out['options']}, {'system:flite', 'system:espeak-ng'})
            self.assertIn('Do not choose a speech engine for the user', out['instructions_for_agent'])
            self.assertIn('recommendations', out)
            self.assertEqual(call('pagecast_voice', {'book_id': book, 'speaker': 'Narrator', 'engine': 'chosen'}, tmp)['state'], 'interview_needed')
            # a person in the dashboard is not interrogated by the model-facing gate
            self.assertNotEqual(call('pagecast_render', {'book_id': book}, tmp, source='ui').get('state'), 'interview_needed')

    def test_answers_without_a_route_are_refused_and_with_one_the_gate_opens(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sr, 'system_tools', tools('flite')):
            book = Books(tmp).import_book(text='Hello there.')['book_id']
            self.assertIn('Ask the user which', call('pagecast_speech_setup', {'answers': ANSWERS}, tmp)['error'])
            self.assertEqual(call('pagecast_render', {'book_id': book}, tmp)['state'], 'interview_needed')
            saved = call('pagecast_speech_setup', {'answers': {**ANSWERS, 'route': 'system:flite'}}, tmp)
            self.assertEqual((saved['state'], saved['you_chose']), ('saved', 'system:flite'))
            self.assertEqual(call('pagecast_speech_setup', {}, tmp)['state'], 'answered')
            self.assertNotEqual(call('pagecast_render', {'book_id': book}, tmp).get('state'), 'interview_needed')

    def test_setup_tool_sends_nothing_and_shows_no_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = call('pagecast_speech_setup', {}, tmp, {'gemini_project': 'proj-secret-1'})
            self.assertNotIn('proj-secret-1', json.dumps(out))


class ChosenEngine(unittest.TestCase):
    def test_default_narrator_is_only_a_placeholder_and_does_not_depend_on_the_computer(self):
        with tempfile.TemporaryDirectory() as tmp:
            for installed in (('espeak-ng',), ('flite', 'espeak-ng'), ()):
                with patch.object(sr, 'system_tools', tools(*installed)):
                    self.assertEqual(Books(tmp)._default_narrator(), {'engine': 'flite', 'voice': 'rms'})

    def answered(self, tmp, route):
        return call('pagecast_speech_setup', {'answers': {**ANSWERS, 'route': route}}, tmp)

    def test_chosen_uses_exactly_the_route_the_user_picked_even_when_others_exist(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sr, 'system_tools', tools('flite', 'espeak-ng')):
            self.answered(tmp, 'system:espeak-ng')
            self.assertEqual(Books(tmp)._chosen_engine(), ('system', {'tool': 'espeak-ng'}))

    def test_chosen_refuses_when_nothing_was_chosen_or_the_choice_vanished(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sr, 'system_tools', tools('flite')):
                with self.assertRaisesRegex(ValueError, 'No speech route has been chosen'):
                    Books(tmp)._chosen_engine()
                self.answered(tmp, 'system:flite')
            with patch.object(sr, 'system_tools', tools()), patch.object(sr, 'find_servers', lambda *a, **k: []):
                with self.assertRaisesRegex(ValueError, 'chose .* is not available now'):
                    Books(tmp)._chosen_engine()

    def test_no_online_answer_blocks_explicit_online_engines_too(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sr, 'system_tools', tools('flite')):
            books = Books(tmp)
            book = books.import_book(text='Hi.')['book_id']
            self.answered(tmp, 'system:flite')
            with self.assertRaisesRegex(ValueError, 'nothing should be sent to an online'):
                books.set_voice(book, 'Narrator', engine='elevenlabs', voice='Rachel')

    @unittest.skipUnless(HAVE_FLITE, 'flite required')
    def test_system_engine_renders_real_audio_offline_and_is_reported_as_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp)
            book = books.import_book(text='Hello there. This is a short test.')['book_id']
            self.answered(tmp, 'system:flite')
            out = call('pagecast_voice', {'book_id': book, 'speaker': 'Narrator', 'engine': 'chosen'}, tmp)
            self.assertEqual(out['voice']['engine'], 'system')
            done = call('pagecast_render', {'book_id': book}, tmp)
            self.assertEqual(done['state'], 'complete')
            row = done['speech_used'][0]
            self.assertEqual((row['engine'], row['billed']), ('system', 'no'))
            self.assertIn('not billed', done['speech_summary'])
            audio = [p for p in Path(tmp).rglob('audio.wav')]
            self.assertTrue(audio)
            with wave.open(str(audio[0])) as w:
                self.assertGreater(w.getnframes(), 1000)


if __name__ == '__main__':
    unittest.main()

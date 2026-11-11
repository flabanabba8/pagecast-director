import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

root = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('pagecast_options_fixture', root/'__init__.py', submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
from pagecast_options_fixture import speech_options, vertex

class SpeechOptionsTests(unittest.TestCase):
    def test_gemini_voice_list_has_thirty_labelled_voices(self):
        names = [v[0] for v in speech_options.GEMINI_VOICES]
        self.assertEqual(len(set(names)), 30)
        by = {n: (g, t) for n, g, t, hz in speech_options.GEMINI_VOICES}
        self.assertTrue(all(hz > 90 for *_, hz in speech_options.GEMINI_VOICES))
        self.assertEqual(by['Algenib'], ('male', 'gravelly')); self.assertEqual(by['Leda'], ('female', 'youthful'))
    def test_unconfigured_route_lists_no_voices_and_shows_no_project(self):
        result = speech_options.speech_options({'higgs_url': 'http://localhost:9'})
        self.assertFalse(result['higgs']['reachable']); self.assertFalse(result['gemini']['configured']); self.assertNotIn('voices', result['gemini'])
    def test_configured_vertex_route_lists_voices_and_never_prints_the_project(self):
        with patch.object(vertex, 'credentials', return_value=object()):
            result = speech_options.speech_options({'gemini_route': 'vertex', 'gemini_project': 'secret-project-id', 'gemini_max_usd': 0.5, 'higgs_url': 'http://localhost:9'})
        self.assertTrue(result['gemini']['configured']); self.assertTrue(result['gemini']['application_default_credentials_found']); self.assertEqual(len(result['gemini']['voices']), 30)
        self.assertNotIn('secret-project-id', str(result))
    def test_tool_is_registered(self):
        self.assertIn('pagecast_speech_options', module.TOOLS); self.assertIn('pagecast_speech_options', (root / 'plugin.yaml').read_text())

if __name__ == '__main__': unittest.main()

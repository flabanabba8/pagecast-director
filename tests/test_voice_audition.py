import http.server
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave

root = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('pagecast_audition_fixture', root/'__init__.py', submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
from pagecast_audition_fixture import voice_audition
from pagecast_audition_fixture.books import Books

PITCHES = iter([110.0, 220.0, 150.0])
SENT = []

def tone(hz, seconds=2.0, rate=24000):
    samples = []
    for n in range(int(seconds * rate)):
        t = n / rate
        samples.append(int(9000 * (math.sin(2 * math.pi * hz * t) + 0.5 * math.sin(4 * math.pi * hz * t) + 0.3 * math.sin(6 * math.pi * hz * t)) / 1.8))
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(struct.pack('<%dh' % len(samples), *samples))
    return out.getvalue()

class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length']))); SENT.append(body)
        data = tone(next(PITCHES))
        self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *args): pass

class AuditionTests(unittest.TestCase):
    def test_candidates_are_measured_kept_and_sent_without_a_reference(self):
        server = http.server.HTTPServer(('localhost', 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp, patch.object(voice_audition, 'PAUSE_SECONDS', 0):
                books = Books(tmp, {'higgs_url': f'http://localhost:{server.server_port}'}); book_id = books.import_book(text='First line.\nSecond line.')['book_id']
                result = voice_audition.audition(books, book_id, 'Mr. Grum', candidates=3)
                self.assertEqual(len(result['candidates']), 3)
                for row, expected in zip(result['candidates'], (110, 220, 150)):
                    self.assertTrue(Path(row['path']).is_file()); self.assertAlmostEqual(row['median_pitch_hz'], expected, delta=expected * 0.05)
                    self.assertEqual(row['reference_text'], voice_audition.DEFAULT_TEXT); self.assertGreater(row['seconds'], 1.5)
                self.assertTrue(all('references' not in body for body in SENT))
                kept = json.loads((Path(result['all_candidates_kept_in']) / 'measurements.json').read_text()); self.assertEqual(len(kept), 3)
                self.assertIn('not a listening review', result['notice'])
        finally:
            server.shutdown(); thread.join(timeout=5); server.server_close()

    def test_bad_arguments_are_refused_before_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); book_id = books.import_book(text='A line.')['book_id']
            for kwargs in ({'candidates': 1}, {'candidates': 13}, {'text': 'Too short.'}, {'text': 'This sentence has control markup [whisper] in it for the test.'}):
                with self.assertRaises(ValueError): voice_audition.audition(books, book_id, 'Pim', **kwargs)
            with self.assertRaises(ValueError): voice_audition.audition(books, 'a' * 32, 'Pim')

    def test_tool_is_registered_in_the_manifest_and_the_tool_table(self):
        self.assertIn('pagecast_voice_audition', module.TOOLS)
        self.assertIn('pagecast_voice_audition', (root / 'plugin.yaml').read_text())

if __name__ == '__main__': unittest.main()

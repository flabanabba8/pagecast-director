import http.server
import importlib.util
import io
import ipaddress
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
import wave

root = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('pagecast_higgs_fixture', root/'__init__.py', submodule_search_locations=[str(root)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
from pagecast_higgs_fixture import higgs, loopback

class Handler(http.server.BaseHTTPRequestHandler):
    payload = None
    auth = None
    def do_POST(self):
        type(self).payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).auth = self.headers.get('Authorization')
        out = io.BytesIO()
        with wave.open(out, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(b'\0\0' * 100)
        data = out.getvalue()
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *args): pass

class HiggsLoopbackTests(unittest.TestCase):
    def test_real_local_http_reference_and_no_auth_header(self):
        server = http.server.HTTPServer(('localhost', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            audio = higgs.synthesize(f'http://localhost:{server.server_port}', 'model', 'Hello.', 'default',
                                     reference_audio='data:audio/wav;base64,AA==', reference_text='Example')
            self.assertTrue(audio.startswith(b'RIFF'))
            self.assertEqual(Handler.payload['references'][0]['text'], 'Example')
            self.assertIsNone(Handler.auth)
        finally:
            server.shutdown(); thread.join(timeout=5); server.server_close()

    def test_resolved_remote_address_is_never_connected(self):
        remote = str(ipaddress.IPv4Address(0x08080808))
        resolved = [(loopback.socket.AF_INET, loopback.socket.SOCK_STREAM, 6, '', (remote, 80))]
        with patch.object(loopback.socket, 'getaddrinfo', return_value=resolved), patch.object(loopback.socket, 'socket') as create:
            with self.assertRaisesRegex(OSError, 'loopback'):
                loopback.LoopbackConnection('localhost', 80, timeout=1).connect()
        create.assert_not_called()

if __name__ == '__main__': unittest.main()

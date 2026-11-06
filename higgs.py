"""Local Higgs TTS3 client, reused from Automatic Tutorial Creator's tested adapter."""
import json
import ipaddress
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .loopback import LoopbackHTTPHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def loopback_host(host):
    if host == 'localhost': return True
    try: return ipaddress.ip_address(host).is_loopback
    except (TypeError, ValueError): return False


def endpoint(base):
    parsed = urlsplit(base)
    if parsed.scheme != 'http' or not loopback_host(parsed.hostname) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('Configure a loopback Higgs server origin, for example http://localhost:8000')
    return base.rstrip('/') + '/v1/audio/speech'


def synthesize(base, model, text, voice, reference_audio='', reference_text=''):
    url = endpoint(base)
    payload = {'model': model, 'input': text, 'voice': voice, 'response_format': 'wav', 'stream': False,
               'temperature': .8, 'top_k': 50, 'top_p': .8, 'max_new_tokens': 2048}
    if reference_audio:
        # The user's local server owns reference access; no voice files are bundled
        # or read by this client. Server-side allowlisting remains in force.
        payload['references'] = [{'audio_path': reference_audio, 'text': reference_text}]
    opener = build_opener(ProxyHandler({}), NoRedirect(), LoopbackHTTPHandler())
    try:
        with opener.open(Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=120) as response:
            data = response.read(32 * 1024 * 1024 + 1)
    except HTTPError as exc:
        raise RuntimeError(f'Higgs returned HTTP {exc.code}; no automatic retry was made') from None
    except (URLError, TimeoutError):
        raise RuntimeError('Local Higgs server unavailable or timed out; start your configured server and retry explicitly') from None
    if len(data) > 32 * 1024 * 1024 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        raise RuntimeError('Higgs did not return a bounded WAV file')
    return data

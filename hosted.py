"""ElevenLabs and Gemini speech; credentials stay in Hermes's secret scope, one request per call, no retries."""
import base64
import binascii
import http.client
import io
import json
import re
import wave

MAX_UNITS = 2000
MAX_RESPONSE = 32 * 1024 * 1024
ELEVEN_MODELS = ('eleven_multilingual_v2', 'eleven_flash_v2_5', 'eleven_turbo_v2_5')
GEMINI_MODEL = re.compile(r'gemini-[0-9]+(?:\.[0-9]+)?-(?:flash-lite|flash|pro)(?:-preview)?-tts(?:-preview)?')


class HostedError(RuntimeError):
    pass


def secret(name, label):
    from .credentials import get_secret
    value = get_secret(name) or ''
    if not isinstance(value, str): raise ValueError(label + ' credential must be configured through Hermes secret settings')
    value = value.strip()
    if not value or len(value) > 4096 or any(not 32 < ord(c) < 127 for c in value):
        raise ValueError('Set the ' + label + ' API key in Hermes Settings > Plugins > PageCast Director')
    return value


def valid_voice(voice, provider):
    if not isinstance(voice, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', voice):
        raise ValueError(f'Use a {provider} voice ID or name made of letters, digits and _ . : -')
    return voice


def units(text):
    return len(text.encode('utf-16-le')) // 2


def post(host, path, headers, payload, provider, observe=None):
    event = observe or (lambda *_: None)
    event('pending', {})
    connection = http.client.HTTPSConnection(host, timeout=90)
    sent = False
    try:
        connection.connect()
        sent = True  # a transport failure from here can have an unknown billed outcome
        connection.request('POST', path, body=json.dumps(payload).encode(), headers={**headers, 'Content-Type': 'application/json', 'User-Agent': 'PageCast-Director/0.1'})
        response = connection.getresponse()
        if response.status != 200:
            event('unknown' if response.status >= 500 else 'rejected', {'http_status': response.status})
            reasons = {400: 'request rejected; check model, voice and text', 401: 'authentication failed', 402: 'payment required; the account is probably out of credits or over its billing limit', 403: 'access denied; check key permissions and credits',
                       404: 'voice or model not found', 422: 'request rejected; check model, voice and text', 429: 'rate/quota limit reached'}
            raise HostedError(f'{provider} HTTP {response.status}: {reasons.get(response.status, "request failed; redirects are never followed")}. No automatic retry was made')
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE: raise ValueError('response exceeds 32 MiB')
        return raw
    except HostedError:
        raise
    except Exception:
        event('unknown' if sent else 'not_sent', {})
        raise HostedError(f'{provider} transport/response failure; the outcome may be unknown. No automatic retry was made') from None
    finally:
        connection.close()


def check_text(text):
    if not isinstance(text, str) or not text.strip() or units(text) > MAX_UNITS:
        raise ValueError('Hosted speech text must contain 1-2000 UTF-16 code units')


def wrap_pcm(pcm, rate=24000):
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return out.getvalue()


def elevenlabs(text, voice, model='eleven_multilingual_v2', observe=None):
    check_text(text); valid_voice(voice, 'ElevenLabs')
    if model not in ELEVEN_MODELS: raise ValueError('Choose a supported ElevenLabs model: ' + ', '.join(ELEVEN_MODELS))
    event = observe or (lambda *_: None)
    key = secret('ELEVENLABS_API_KEY', 'ElevenLabs')
    raw = post('api.elevenlabs.io', f'/v1/text-to-speech/{voice}?output_format=pcm_24000', {'xi-api-key': key}, {'text': text, 'model_id': model}, 'ElevenLabs', observe)
    usage = {'reported_units': None, 'requested_utf16_units': units(text), 'model_id': model}
    event('received', usage)
    if len(raw) < 480 or len(raw) % 2: 
        event('audio_invalid', usage)
        raise HostedError('ElevenLabs returned unusable PCM audio; no paid retry was made')
    return wrap_pcm(raw), usage


def _audio_item(node):
    if isinstance(node, dict):
        if node.get('type') == 'audio' and isinstance(node.get('data'), str): return node
        for value in node.values():
            found = _audio_item(value)
            if found: return found
    elif isinstance(node, list):
        for value in node:
            found = _audio_item(value)
            if found: return found
    return None


def gemini(text, voice, model='gemini-3.8-flash-tts', observe=None):
    check_text(text); valid_voice(voice, 'Gemini')
    if not isinstance(model, str) or not GEMINI_MODEL.fullmatch(model): raise ValueError('Use a Gemini speech model ID such as gemini-3.8-flash-tts')
    event = observe or (lambda *_: None)
    key = secret('GEMINI_API_KEY', 'Gemini')
    body = {'model': model, 'input': [{'type': 'user_input', 'content': [{'type': 'text', 'text': text}]}],
            'response_format': {'type': 'audio', 'mime_type': 'audio/wav', 'sample_rate': 24000},
            'generation_config': {'speech_config': [{'voice': voice}]}}
    raw = post('generativelanguage.googleapis.com', '/v1beta/interactions', {'x-goog-api-key': key}, body, 'Gemini', observe)
    usage = {'reported_units': None, 'requested_utf16_units': units(text), 'model_id': model}
    event('received', usage)
    try:
        item = _audio_item(json.loads(raw))
        audio = base64.b64decode(item['data'], validate=True)
        if audio[:4] != b'RIFF' or audio[8:12] != b'WAVE': raise ValueError('not WAV')
    except (ValueError, TypeError, KeyError, binascii.Error):
        event('audio_invalid', usage)
        raise HostedError('Gemini returned no valid WAV audio; no paid retry was made') from None
    return audio, usage

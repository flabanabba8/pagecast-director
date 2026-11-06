"""Inworld's native synchronous TTS API; credentials stay in Hermes's scope."""
import base64
import binascii
import http.client
import json
import re
from urllib.parse import urlencode

HOST = 'api.inworld.ai'
MODELS = ('inworld-tts-2', 'inworld-tts-2-flash')


class InworldError(RuntimeError):
    pass


def credential():
    from agent.secret_scope import get_secret
    value = get_secret('INWORLD_API_KEY') or ''
    if not isinstance(value, str): raise ValueError('Inworld credential must be configured through Hermes secret settings')
    value = value.strip()
    if value.lower().startswith('basic '): value = value[6:].strip()
    if not value or len(value) > 4096 or any(not 32 < ord(c) < 127 for c in value):
        raise ValueError('Set the copied Inworld API credential in Hermes Settings → Plugins → PageCast Director')
    return value


def units(text):
    return len(text.encode('utf-16-le')) // 2


def valid_voice(voice):
    if not isinstance(voice, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', voice):
        raise ValueError('Use an Inworld voiceId from the voice catalog, not its display name or resource path')
    return voice


def request(method, path, payload=None, observe=None):
    key = credential()
    event = observe or (lambda *_: None)
    event('pending', {})
    connection = http.client.HTTPSConnection(HOST, timeout=45)
    sent = False
    try:
        connection.connect()
        headers = {'Authorization': 'Basic ' + key, 'Content-Type': 'application/json', 'User-Agent': 'PageCast-Director/0.1'}
        sent = True  # a transport failure from here can have an unknown billed outcome
        connection.request(method, path, body=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            event('unknown' if response.status >= 500 else 'rejected', {'http_status': response.status})
            reasons = {401: 'authentication failed', 403: 'access denied; check speech permission, credits and voice access',
                       404: 'voice or model not found', 429: 'rate/quota limit reached'}
            reason = reasons.get(response.status, 'request failed; redirects are never followed')
            if response.status == 403 and method == 'GET' and path.startswith('/voices/'):
                reason = 'voice catalog access denied; enter a known voice ID or check voice-list permissions'
            raise InworldError(f'Inworld HTTP {response.status}: {reason}. No automatic retry was made')
        raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024: raise ValueError('response exceeds32 MiB')
        data = json.loads(raw)
        if not isinstance(data, dict): raise ValueError('response is not an object')
        return data
    except InworldError:
        raise
    except Exception:
        event('unknown' if sent else 'not_sent', {})
        raise InworldError('Inworld transport/response failure; the outcome may be unknown. No automatic retry was made') from None
    finally:
        connection.close()


def synthesize(text, voice, model='inworld-tts-2', observe=None):
    if not isinstance(text, str) or not text.strip() or units(text) > 2000:
        raise ValueError('Inworld text must contain1–2000 UTF-16 code units')
    valid_voice(voice)
    if model not in MODELS: raise ValueError('Choose inworld-tts-2 or inworld-tts-2-flash')
    event = observe or (lambda *_: None)
    data = request('POST', '/tts/v1/voice', {'text': text, 'voiceId': voice, 'modelId': model,
        'deliveryMode': 'BALANCED', 'audioConfig': {'audioEncoding': 'LINEAR16', 'sampleRateHertz': 48000}}, observe)
    raw_usage = data.get('usage') or {}
    if not isinstance(raw_usage, dict): raw_usage = {}
    reported = raw_usage.get('processedCharactersCount', raw_usage.get('processed_characters_count'))
    if isinstance(reported, str) and reported.isdigit(): reported = int(reported)
    if isinstance(reported, bool) or not isinstance(reported, int) or not 0 <= reported <= 10_000_000: reported = None
    reported_model = raw_usage.get('modelId', raw_usage.get('model_id', model))
    usage = {'reported_units': reported, 'requested_utf16_units': units(text),
             'model_id': reported_model if reported_model in MODELS else model}
    event('received', usage)  # keep usage even if the paid audio payload is malformed
    try:
        encoded = data.get('audioContent', data.get('audio_content'))
        if not isinstance(encoded, str) or not encoded: raise ValueError('empty audio')
        audio = base64.b64decode(encoded, validate=True)
        if audio[:4] != b'RIFF' or audio[8:12] != b'WAVE': raise ValueError('not WAV')
    except (ValueError, binascii.Error):
        event('audio_invalid', usage)
        raise InworldError('Inworld returned invalid WAV/base64 audio; usage was retained and no paid retry was made') from None
    return audio, usage


def voices(page_token='', include_custom=False):
    if not isinstance(page_token, str) or len(page_token) > 2048 or not isinstance(include_custom, bool):
        raise ValueError('Invalid voice-list pagination request')
    query = {'pageSize': 100, 'pageToken': page_token}
    if not include_custom: query['filter'] = 'source="SYSTEM"'
    data = request('GET', '/voices/v1/voices?' + urlencode(query))
    items = []
    for voice in data.get('voices', [])[:100]:
        identifier = voice.get('voiceId')
        valid_voice(identifier)
        items.append({'id': identifier, 'name': str(voice.get('displayName', identifier))[:200],
                      'language': str(voice.get('languageCode', voice.get('langCode', '')))[:40]})
    return {'voices': items, 'next_page_token': data.get('nextPageToken') or '', 'custom_included': include_custom}

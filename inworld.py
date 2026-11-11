"""Inworld's native synchronous TTS API; credentials stay in Hermes's scope."""
import base64
import binascii
import http.client
import json
import math
import re
import ssl
import socket
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlencode

HOST = 'api.inworld.ai'
MODELS = ('inworld-tts-2', 'inworld-tts-2-flash')


class InworldError(RuntimeError):
    pass


class InworldConnection(http.client.HTTPSConnection):
    def connect(self):
        # TLS setup may be intermittent on this route. Retry only before ANY
        # HTTP request is sent; synthesis/authentication responses are never retried.
        for attempt in range(3):
            raw = None
            try:
                raw = socket.create_connection((self.host, self.port), timeout=5, source_address=self.source_address)
                # Preserve TCP buffering: the successful live synthesis used it.
                self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
                self.sock.settimeout(self.timeout)
                return
            except (TimeoutError, ConnectionResetError, BrokenPipeError):
                if raw is not None: raw.close()
                if attempt == 2: raise
            except BaseException:
                if raw is not None: raw.close()
                raise


_session = ContextVar('pagecast_inworld_session', default=None)


@contextmanager
def session():
    """Reuse verified HTTP keep-alive within one render; never replay a request."""
    if _session.get() is not None:
        yield
        return
    state = {'connection': None}
    token = _session.set(state)
    try: yield
    finally:
        if state['connection'] is not None: state['connection'].close()
        _session.reset(token)


def credential():
    from .credentials import get_secret
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
    if not isinstance(voice, str) or not re.fullmatch(r'[\w.:-]{1,256}', voice):
        raise ValueError('Use an Inworld voiceId from the voice catalog, not its display name or resource path')
    return voice


def request(method, path, payload=None, observe=None):
    key = credential()
    event = observe or (lambda *_: None)
    event('pending', {})
    # OpenSSL 3.5 default negotiation stalls on the tested Inworld route.
    # TLS 1.2 with verified ECDHE/AES-GCM works; scope compatibility to this host.
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    state = _session.get()
    connection = state['connection'] if state is not None else None
    if connection is None:
        connection = InworldConnection(HOST, timeout=45, context=context)
        if state is not None: state['connection'] = connection
    sent = False
    keep = False
    try:
        if getattr(connection, 'sock', None) is None: connection.connect()
        headers = {'Authorization': 'Basic ' + key, 'Content-Type': 'application/json', 'User-Agent': 'PageCast-Director/0.1'}
        sent = True  # a transport failure from here can have an unknown billed outcome
        connection.request(method, path, body=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            event('unknown' if response.status >= 500 else 'rejected', {'http_status': response.status})
            reasons = {401: 'authentication failed', 402: 'payment required; the account is probably out of credits or over its billing limit', 403: 'access denied; check speech permission, credits and voice access',
                       404: 'voice or model not found', 429: 'rate/quota limit reached'}
            reason = reasons.get(response.status, 'request failed; redirects are never followed')
            if response.status == 403 and method == 'GET' and path.startswith('/voices/'):
                reason = 'voice catalog access denied; enter a known voice ID or check voice-list permissions'
            raise InworldError(f'Inworld HTTP {response.status}: {reason}. No automatic retry was made')
        raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024: raise ValueError('response exceeds32 MiB')
        data = json.loads(raw)
        if not isinstance(data, dict): raise ValueError('response is not an object')
        keep = state is not None and not getattr(response, 'will_close', False)
        return data
    except InworldError:
        raise
    except Exception:
        event('unknown' if sent else 'not_sent', {})
        raise InworldError('Inworld transport/response failure; the outcome may be unknown. No automatic retry was made' if sent else 'Could not establish an Inworld TLS connection. No synthesis request was sent; no automatic retry was made') from None
    finally:
        if not keep:
            connection.close()
            if state is not None: state['connection'] = None


def options(value=None, model='inworld-tts-2'):
    """Validate exposed synthesis controls before any paid request."""
    value = {} if value is None else value
    if not isinstance(value, dict): raise ValueError('Inworld options must be an object')
    allowed = {'deliveryMode', 'speakingRate', 'language', 'timestampType', 'applyTextNormalization',
               'enhanceGeneration', 'enableCustomPronunciation', 'reasoning', 'reasoningContext', 'previousTexts', 'temperature', 'lipsync', 'pronunciationDictionarySettings'}
    if set(value) - allowed: raise ValueError('Unknown Inworld option')
    result = dict(value)
    for key, choices in {'deliveryMode': ('STABLE', 'BALANCED', 'CREATIVE'), 'timestampType': ('WORD', 'CHARACTER', 'TIMESTAMP_TYPE_UNSPECIFIED'),
                         'applyTextNormalization': ('ON', 'OFF', 'APPLY_TEXT_NORMALIZATION_UNSPECIFIED')}.items():
        if key in result and result[key] not in choices: raise ValueError('Invalid ' + key)
    for key, low, high in [('speakingRate', .5, 1.5), ('temperature', .000001, 2)]:
        if key in result and (type(result[key]) not in (int, float) or not math.isfinite(result[key]) or not low <= result[key] <= high): raise ValueError('Invalid ' + key)
    for key in ('enhanceGeneration', 'enableCustomPronunciation', 'reasoning', 'lipsync'):
        if key in result and type(result[key]) is not bool: raise ValueError('Invalid ' + key)
    for key, maximum in [('language', 80), ('reasoningContext', 600)]:
        if key in result and (not isinstance(result[key], str) or len(result[key]) > maximum): raise ValueError('Invalid ' + key)
    previous = result.get('previousTexts', [])
    if not isinstance(previous, list) or len(previous) > 5 or any(not isinstance(t, str) for t in previous) or sum(units(t) for t in previous) > 2000: raise ValueError('Previous context allows five texts and 2000 UTF-16 units')
    if model != 'inworld-tts-2' and any(result.get(k) for k in ('reasoning', 'reasoningContext', 'deliveryMode', 'enableCustomPronunciation')):
        raise ValueError('Steering, reasoning, delivery mode and custom pronunciation require Inworld TTS-2')
    if model == 'inworld-tts-2' and 'temperature' in result: raise ValueError('TTS-2 uses deliveryMode, not temperature')
    if result.get('enableCustomPronunciation') and not result.get('language'): raise ValueError('Custom pronunciation requires a language')
    dictionaries = result.get('pronunciationDictionarySettings')
    if dictionaries is not None:
        if 'enableCustomPronunciation' in result: raise ValueError('Choose workspace pronunciations or named dictionaries, not both')
        if model != 'inworld-tts-2' or not result.get('language'): raise ValueError('Named dictionaries require TTS-2 and a language')
        if not isinstance(dictionaries, dict) or set(dictionaries) != {'dictionaries'}: raise ValueError('Invalid dictionary settings')
        entries = dictionaries['dictionaries']
        if not isinstance(entries, list) or not 1 <= len(entries) <= 3: raise ValueError('Choose 1–3 named dictionaries')
        names = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'dictionary'} or not isinstance(entry['dictionary'], str) or not re.fullmatch(r'workspaces/[A-Za-z0-9_-]+/pronunciationDictionaries/[A-Za-z0-9_-]+', entry['dictionary']): raise ValueError('Use complete dictionary resource names')
            names.append(entry['dictionary'])
        if len(set(names)) != len(names): raise ValueError('Duplicate pronunciation dictionary')
    return result


def synthesize(text, voice, model='inworld-tts-2', observe=None, controls=None):
    if not isinstance(text, str) or not text.strip() or units(text) > 2000:
        raise ValueError('Inworld text must contain1–2000 UTF-16 code units')
    valid_voice(voice)
    if model not in MODELS: raise ValueError('Choose inworld-tts-2 or inworld-tts-2-flash')
    event = observe or (lambda *_: None)
    control = options(controls, model)
    payload = {'text': text, 'voiceId': voice, 'modelId': model,
               'audioConfig': {'audioEncoding': 'LINEAR16', 'sampleRateHertz': 48000}}
    if model == 'inworld-tts-2': payload['deliveryMode'] = 'BALANCED'
    for key in ('deliveryMode', 'language', 'timestampType', 'applyTextNormalization', 'enhanceGeneration', 'enableCustomPronunciation', 'temperature', 'pronunciationDictionarySettings'):
        if key in control: payload[key] = control[key]
    if 'speakingRate' in control: payload['audioConfig']['speakingRate'] = control['speakingRate']
    context = {}
    if control.get('reasoning'): context['reasoning'] = 'REASONING_ON'
    if control.get('reasoningContext'): context['reasoningContext'] = control['reasoningContext']
    if control.get('previousTexts'): context['previousRequests'] = [{'text': t} for t in control['previousTexts']]
    if context: payload['synthesisContext'] = context
    if control.get('lipsync'): payload['lipsyncConfig'] = {'visemeSet': 'OPENXR'}
    data = request('POST', '/tts/v1/voice', payload, observe)
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
    usage['timestamp_info'] = data.get('timestampInfo', {})
    usage['reasoning_instruction'] = data.get('reasoningInstruction', '')
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


def performance_text(text, pronunciations=None):
    """Apply explicit one-word IPA substitutions without changing reader text."""
    pronunciations = {} if pronunciations is None else pronunciations
    if not isinstance(pronunciations, dict) or len(pronunciations) > 100: raise ValueError('Use at most 100 pronunciation substitutions')
    for word, ipa in pronunciations.items():
        if not isinstance(word, str) or not word or len(word) > 80 or any(c in word for c in '[]<>/\n'):
            raise ValueError('Invalid pronunciation word')
        if not isinstance(ipa, str) or not re.fullmatch(r'/[^\s/\[\]<>]{1,160}/', ipa): raise ValueError('Use a single English IPA word wrapped in slashes')
    parts = re.split(r'(\[[^\]\n]*\]|<[^>]*>)', text)
    for index in range(0, len(parts), 2):
        # One substitution pass: replacements cannot cascade through other entries.
        if pronunciations:
            pattern = r'(?<!\w)(?:' + '|'.join(re.escape(w) for w in sorted(pronunciations, key=len, reverse=True)) + r')(?!\w)'
            parts[index] = re.sub(pattern, lambda match: pronunciations[match.group()], parts[index])
    result = ''.join(parts)
    if units(result) > 2000: raise ValueError('Performance including IPA exceeds 2000 UTF-16 units')
    return result

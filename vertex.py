"""Vertex Gemini speech with ADC, persistent usage accounting and no POST retries."""
import base64
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import json
import re
import time

from .hosted import HostedError, check_text, valid_voice, MAX_RESPONSE

_active = ContextVar('pagecast_vertex_session', default=None)
# Conservative full list rates; promotional credits are not assumed.
INPUT_USD = 1 / 1_000_000
OUTPUT_USD = 18 / 1_000_000
# Hard ceiling of one request (8192 in + 16384 out tokens); also the cost of the largest text.
RESERVATION = 8192 * INPUT_USD + 16384 * OUTPUT_USD
MIN_RESERVATION = 0.005


def estimate_usd(text):
    """Safe upper estimate for one request, from the text length.

    Input: one token per UTF-16 unit plus a small overhead (real text is about 0.25 per character).
    Output: audio is 25 tokens per second; assume a slow 7 characters per second, about twice
    the real cost. Never below MIN_RESERVATION, never above the per-request ceiling.
    """
    units = len(text.encode('utf-16-le')) // 2
    cost = (units + 64) * INPUT_USD + (units * 3.6 + 100) * OUTPUT_USD
    return min(RESERVATION, max(MIN_RESERVATION, cost))


@lru_cache(maxsize=1)
def credentials():
    import google.auth
    return google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0]


@contextmanager
def session():
    current = _active.get()
    if current is not None:
        yield current
        return
    import requests
    with requests.Session() as client:
        token = _active.set(client)
        try: yield client
        finally: _active.reset(token)


def save(path, ledger):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(ledger, indent=2)); temporary.chmod(0o600)
    temporary.replace(path)


def usage(path):
    """Read reported token counts without exposing request, project or credential data."""
    if not path.exists(): return None
    try:
        rows = json.loads(path.read_text())
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError('Invalid usage ledger')
    except (OSError, ValueError):
        return {'available': False}
    def has_tokens(row):
        return all(type(row.get(key)) is int and row[key] >= 0 for key in ('input_tokens', 'output_tokens'))
    reported = [row for row in rows if has_tokens(row)]
    return {'available': True, 'attempts': len(rows),
            'received': sum(row.get('status') == 'received' for row in rows),
            'unknown_requests': sum(row.get('status') in ('pending', 'unknown') for row in rows),
            'input_tokens': sum(row['input_tokens'] for row in reported),
            'output_tokens': sum(row['output_tokens'] for row in reported),
            'unreported_usage_requests': sum(row.get('status') in ('received', 'audio_invalid')
                and not has_tokens(row) for row in rows)}


def synthesize(text, voice, model, observe, *, project, ledger_path, max_usd=3):
    check_text(text); valid_voice(voice, 'Vertex')
    if not isinstance(project, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', project):
        raise ValueError('Configure a Google Cloud project for Vertex speech')
    if model not in ('gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts'):
        raise ValueError('Vertex speech requires a supported Gemini 3.8 TTS model')
    if isinstance(max_usd, bool) or not isinstance(max_usd, (int, float)) or not 0 < max_usd <= 100:
        raise ValueError('Set a Vertex book budget between 0 and 100 USD')
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    estimate = estimate_usd(text)
    spent = sum(row['reserved_or_actual_usd'] for row in ledger)
    if spent + estimate > max_usd:
        raise HostedError(f'Vertex book spending guard reached; no speech request sent. This request is estimated at '
                          f'up to {estimate:.4f} USD and {spent:.4f} USD is already used or reserved, against a guard of '
                          f'{max_usd:g} USD. Raise the gemini_max_usd setting, or render fewer or shorter passages.')
    event = observe or (lambda *_: None)
    usage = {'reported_units': None, 'requested_utf16_units': len(text.encode('utf-16-le')) // 2, 'model_id': model, 'route': 'vertex'}
    try:
        from google.auth.transport.requests import Request
        cred = credentials()
        if not cred.valid: cred.refresh(Request())
    except Exception:
        event('not_sent', usage)
        raise HostedError('Vertex ADC refresh failed before speech transmission; no POST sent') from None
    base = f'https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/{model}:generateContent'
    body = {'contents': [{'role': 'user', 'parts': [{'text': text}]}], 'generationConfig': {
        'responseModalities': ['AUDIO'], 'speechConfig': {'voiceConfig': {'voice': voice}}}}
    with session() as client:
        headers = {'Authorization': 'Bearer ' + cred.token, 'x-goog-user-project': project}
        if client.headers.get('x-goog-user-project') != project:
            # Bounded unbilled connection setup only; the speech POST is never retried.
            last_error = 'connection unavailable'
            for attempt in range(2):
                try:
                    warm = client.head('https://aiplatform.googleapis.com/', headers={'User-Agent': 'PageCast-Director'}, timeout=(8, 8), allow_redirects=False)
                    if warm.status_code not in (200, 404):
                        last_error = 'HTTP ' + str(warm.status_code)
                        continue
                    break
                except Exception as exc:
                    last_error = type(exc).__name__
            else:
                event('not_sent', usage)
                raise HostedError(f'Vertex connection preflight failed ({last_error}); no speech POST sent') from None
            client.headers['x-goog-user-project'] = project
        row = {'started': time.time(), 'status': 'pending', 'reserved_or_actual_usd': estimate}
        ledger.append(row); save(ledger_path, ledger); event('pending', usage)
        try:
            response = client.post(base, headers=headers, json=body, timeout=(60, 240), allow_redirects=False)
        except Exception:
            row['status'] = 'unknown'; save(ledger_path, ledger); event('unknown', usage)
            raise HostedError('Vertex transport failure; billed outcome unknown; no retry made') from None
        if response.status_code != 200:
            status = 'rejected' if 400 <= response.status_code < 500 else 'unknown'
            row['status'] = status
            try: message = str(response.json().get('error', {}).get('message', ''))[:2000]
            except Exception: message = ''
            row['error_message'] = message.replace(project, '<project>').replace(voice, '<voice>')
            if status == 'rejected': row['reserved_or_actual_usd'] = 0
            save(ledger_path, ledger); event(status, {**usage, 'http_status': response.status_code})
            raise HostedError(f'Vertex HTTP {response.status_code}: {row["error_message"]}; no retry made')
        try:
            if len(response.content) > MAX_RESPONSE: raise ValueError('response too large')
            result = response.json(); metadata = result.get('usageMetadata', {})
            input_tokens = metadata.get('promptTokenCount'); output_tokens = metadata.get('candidatesTokenCount')
            if type(input_tokens) is int and type(output_tokens) is int and input_tokens >= 0 and output_tokens >= 0:
                row.update(input_tokens=input_tokens, output_tokens=output_tokens,
                           reserved_or_actual_usd=input_tokens * INPUT_USD + output_tokens * OUTPUT_USD)
            row['status'] = 'received'; save(ledger_path, ledger)
            usage['usage_metadata'] = metadata; event('received', usage)
            candidates = result.get('candidates', [])
            if len(candidates) != 1 or candidates[0].get('finishReason') != 'STOP': raise ValueError('incomplete response')
            parts = candidates[0].get('content', {}).get('parts', [])
            audio_parts = [part['inlineData'] for part in parts if 'inlineData' in part]
            if len(audio_parts) != 1: raise ValueError('missing audio')
            audio = base64.b64decode(audio_parts[0]['data'], validate=True)
            if audio[:4] != b'RIFF' or audio[8:12] != b'WAVE': raise ValueError('expected WAV')
        except Exception:
            row['status'] = 'audio_invalid'; save(ledger_path, ledger); event('audio_invalid', usage)
            raise HostedError('Vertex returned incomplete or invalid audio; no retry made') from None
    return audio, usage

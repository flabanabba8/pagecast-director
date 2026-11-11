"""Audition candidate voices for one speaker: Higgs (reference-based) or the configured Gemini route.

A server without a reference clip invents a new voice on every request. This tool
asks it for a few short takes of one neutral sentence, measures each take without
any model (length, median pitch, loudness), keeps them in the book's private
folder, and lets the agent lock the best fit with pagecast_voice (the chosen take
as reference_audio plus its exact text as reference_text). Auditions are not book
lines and never replace a locked voice.
"""
import array
import json
import math
from pathlib import Path
import re
import sys
import time
import wave

from .higgs import synthesize
from . import hosted, vertex

DEFAULT_TEXT = 'Good evening. The last ferry leaves in a few minutes, so please keep your bags close.'
PAUSE_SECONDS = 3


def measure(path):
    """Length, rough median pitch (autocorrelation, 60-400 Hz), voiced share and loudness. No model."""
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth()) != (1, 2): raise ValueError('Audition take must be mono 16-bit PCM')
        rate = wav.getframerate(); raw = wav.readframes(wav.getnframes())
    samples = array.array('h'); samples.frombytes(raw)
    if sys.byteorder != 'little': samples.byteswap()
    seconds = len(samples) / rate
    import numpy as np
    x = np.asarray(samples, dtype=np.float64) / 32768
    rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
    frame, hop = int(rate * 0.04), int(rate * 0.01); low, high = int(rate / 400), int(rate / 60)
    pitches, frames = [], 0
    for start in range(0, len(x) - frame - high, hop):
        chunk = x[start:start + frame + high]; seg = chunk[:frame] - chunk[:frame].mean()
        energy = float(np.dot(seg, seg))
        if energy < 1e-4 * frame: continue
        frames += 1
        scores = np.array([np.dot(seg, chunk[lag:lag + frame] - chunk[lag:lag + frame].mean()) for lag in range(low, high + 1)])
        best = int(np.argmax(scores))
        if scores[best] / energy > 0.5: pitches.append(rate / (low + best))
    return {'seconds': round(seconds, 2), 'median_pitch_hz': round(float(np.median(pitches)), 1) if len(pitches) >= 5 else None,
            'voiced_share': round(len(pitches) / frames, 2) if frames else 0.0, 'loudness_dbfs': round(20 * math.log10(rms), 1) if rms > 0 else None}


def audition(books, book_id, speaker, candidates=6, text=None, engine=None, voices=None):
    if engine is None: engine = 'gemini' if voices is not None else 'higgs'
    if engine == 'gemini': return audition_gemini(books, book_id, speaker, voices, text)
    if engine != 'higgs': raise ValueError('Audition supports engine higgs (invented reference voices) or gemini (named voices)')
    if voices is not None: raise ValueError('voices applies to engine gemini only')
    folder = books.folder(book_id)
    if not isinstance(speaker, str) or not 1 <= len(speaker.strip()) <= 80: raise ValueError('Choose the speaker to audition')
    if type(candidates) is not int or not 2 <= candidates <= 12: raise ValueError('Audition 2 to 12 candidates')
    text = DEFAULT_TEXT if text is None else text
    if not isinstance(text, str) or not 8 <= len(text.split()) <= 40 or re.search(r'[\[\]<>{}|]', text): raise ValueError('Audition text: 8 to 40 plain words, no control markup')
    endpoint = books.settings.get('higgs_url', 'http://localhost:8000'); model = books.settings.get('higgs_model', 'bosonai/higgs-tts-3-4b')
    label = re.sub(r'[^A-Za-z0-9]+', '-', speaker).strip('-').lower() or 'speaker'
    out = folder / 'auditions' / label; out.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = len(list(out.glob('candidate-*.wav'))); rows = []
    from .books import trim_higgs_padding
    for number in range(existing + 1, existing + candidates + 1):
        if rows: time.sleep(PAUSE_SECONDS)
        path = out / f'candidate-{number}.wav'
        path.write_bytes(synthesize(endpoint, model, text, 'default')); path.chmod(0o600)
        trim_higgs_padding(path)
        row = {'candidate': number, 'path': str(path), 'reference_text': text, **measure(path)}
        rows.append(row)
    record = out / 'measurements.json'
    previous = json.loads(record.read_text()) if record.is_file() else []
    record.write_text(json.dumps(previous + rows, indent=2) + '\n'); record.chmod(0o600)
    ranked = sorted((r for r in rows if r['median_pitch_hz']), key=lambda r: r['median_pitch_hz'])
    return {'speaker': speaker, 'candidates': rows, 'by_pitch_low_to_high': [{'candidate': r['candidate'], 'median_pitch_hz': r['median_pitch_hz']} for r in ranked], 'all_candidates_kept_in': str(out),
            'how_to_choose': 'Invented voices cluster around 170-240 Hz and low ones are rare, so audition more candidates (up to 12 per call, call again for more; earlier candidates are kept) rather than ask the user for a sample. Pick the candidate whose pitch fits the character, e.g. a deep man 80-125 Hz, a typical man 100-150 Hz, a typical woman 165-255 Hz, a steady narrator in between or clearly apart from the characters; give every speaker a different candidate. Then call pagecast_voice with engine higgs, voice default, reference_audio set to the candidate path and reference_text set to its reference_text, so every passage of that speaker uses this voice.',
            'notice': 'Each audition request invents a new voice (no reference was sent). Pitch is a rough measured guide, not a listening review. Auditions are not rerolls of book lines; nothing was assigned or locked.'}


def audition_gemini(books, book_id, speaker, voices, text=None):
    """One short line per named Gemini voice, same spend guard as rendering. Nothing is added to the book."""
    from .speech_options import GEMINI_VOICES
    known = [name for name, *_ in GEMINI_VOICES]
    folder = books.folder(book_id)
    if not isinstance(speaker, str) or not 1 <= len(speaker.strip()) <= 80: raise ValueError('Choose the speaker to audition')
    if not isinstance(voices, list) or not 2 <= len(voices) <= 6 or any(not isinstance(v, str) for v in voices) or len(set(voices)) != len(voices):
        raise ValueError('Name 2 to 6 different Gemini voices to audition. Options: ' + ', '.join(known))
    unknown = [v for v in voices if v not in known]
    if unknown: raise ValueError('Not a Gemini prebuilt voice: ' + ', '.join(unknown) + '. Nothing was requested and nothing was billed. Options: ' + ', '.join(known))
    text = DEFAULT_TEXT if text is None else text
    if not isinstance(text, str) or not 8 <= len(text.split()) <= 40 or re.search(r'[\[\]<>{}|]', text): raise ValueError('Audition text: 8 to 40 plain words, no control markup')
    settings = books.settings
    route = settings.get('gemini_route') or ''
    if route not in ('vertex', 'developer'): raise ValueError('Gemini is not configured (gemini_route). Nothing was requested and nothing was billed. Use engine higgs, or configure Gemini first (pagecast_speech_options shows what is usable)')
    model = settings.get('gemini_model', 'gemini-3.8-flash-tts')
    if not isinstance(model, str) or not hosted.GEMINI_MODEL.fullmatch(model): raise ValueError('Use a Gemini speech model ID such as gemini-3.8-flash-tts')
    max_usd = settings.get('gemini_max_usd', 3)
    estimate = vertex.estimate_usd(text)
    ledger_path = folder / 'vertex-usage.json'
    if route == 'vertex':
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
        spent = sum(row['reserved_or_actual_usd'] for row in ledger)
    else: spent = 0.0  # the developer route keeps no ledger; the guard covers this call only
    need = estimate * len(voices)
    if isinstance(max_usd, bool) or not isinstance(max_usd, (int, float)) or not 0 < max_usd <= 100: raise ValueError('Set a Gemini book budget between 0 and 100 USD (gemini_max_usd)')
    if spent + need > max_usd:
        raise ValueError(f'Spending guard: {len(voices)} audition lines are estimated at up to {need:.4f} USD and {spent:.4f} USD is already used or reserved, against a guard of {max_usd:g} USD. Nothing was requested and nothing was billed. Audition fewer voices, or raise the gemini_max_usd setting.')
    label = re.sub(r'[^A-Za-z0-9]+', '-', speaker).strip('-').lower() or 'speaker'
    out = folder / 'auditions' / (label + '-gemini'); out.mkdir(parents=True, exist_ok=True, mode=0o700)
    rows, stopped = [], None
    with books_session(route):
        for voice in voices:
            if rows: time.sleep(PAUSE_SECONDS)
            before = sum(r['reserved_or_actual_usd'] for r in json.loads(ledger_path.read_text())) if route == 'vertex' and ledger_path.exists() else 0.0
            try:
                if route == 'vertex': audio, _ = vertex.synthesize(text, voice, model, None, project=settings.get('gemini_project', ''), ledger_path=ledger_path, max_usd=max_usd)
                else: audio, _ = hosted.gemini(text, voice, model)
            except Exception as exc:
                stopped = {'voice': voice, 'error': str(exc) if isinstance(exc, (ValueError, hosted.HostedError)) else 'request failed', 'note': 'No further voices were requested and nothing was retried. A failed paid request may still have been billed; check pagecast_usage.'}
                break
            path = out / f'{voice.lower()}.wav'; path.write_bytes(audio); path.chmod(0o600)
            after = sum(r['reserved_or_actual_usd'] for r in json.loads(ledger_path.read_text())) if route == 'vertex' else 0.0
            cost, basis = (round(after - before, 6), 'reported tokens (or reserved estimate when the provider reported none)') if route == 'vertex' else (round(estimate, 6), 'upper estimate from text length; no usage ledger on this route')
            try: seconds = measure(path)['seconds']
            except Exception: seconds = None
            rows.append({'engine': 'gemini', 'voice': voice, 'model': model, 'route': route, 'seconds': seconds, 'cost_usd_estimate': cost, 'cost_basis': basis, 'billed': 'yes', 'reference_text': text, 'path': str(path)})
    total = round(sum(r['cost_usd_estimate'] for r in rows), 6)
    summary = f"Auditioned {len(rows)} Gemini voice(s) ({', '.join(r['voice'] for r in rows)}) on the {route} route with {model}: BILLED, about {total} USD in total. Nothing was added to the book and no voice was locked." if rows else 'No audition was made and nothing was billed.'
    return {'speaker': speaker, 'engine': 'gemini', 'candidates': rows, 'billed': 'yes' if rows else 'unknown' if stopped else 'no', 'total_cost_usd_estimate': total, 'speech_summary': summary,
            'stopped': stopped, 'kept_in': str(out),
            'how_to_choose': 'Listen to the files (or ask the user), then lock the chosen one with pagecast_voice (engine gemini, voice = the name). Named Gemini voices are fixed, so no reference clip is needed.',
            'notice': 'Each line was one paid Gemini request with a fixed named voice. Audition lines are not book passages; nothing was assigned or locked.'}


def books_session(route):
    from contextlib import nullcontext
    return vertex.session() if route == 'vertex' else nullcontext()

"""Audition candidate voices for one speaker on a reference-based speech server (Higgs).

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


def audition(books, book_id, speaker, candidates=6, text=None):
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

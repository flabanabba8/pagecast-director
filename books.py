"""Editable passage/cast state and content-addressed render bookkeeping."""
from contextlib import contextmanager
import base64
import fcntl
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
import threading
import uuid
import wave

from .higgs import synthesize
from .reference_paths import resolve_reference
from . import inworld
from .process_env import process_env
from .importers import MAX_TEXT, import_file, segment

FLITE_VOICES = ('rms', 'slt', 'awb', 'kal16', 'kal')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run(args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=process_env())
    if result.returncode: raise RuntimeError(Path(args[0]).name + ' failed: ' + result.stderr[-600:])
    return result.stdout


def inspect_wav(path):
    with wave.open(str(path), 'rb') as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 24000 or wav.getnframes() <= 0:
            raise ValueError('Expected nonempty mono24kHz16-bit PCM')
        expected = wav.getnframes() * 2
        data = wav.readframes(wav.getnframes())
        if len(data) != expected: raise ValueError('Truncated rendered audio')
        return wav.getnframes() / 24000


def verify_cache(path, full=True):
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink(): raise ValueError('Symlinked audio cache is unsupported')
    def identity(value): return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    try:
        receipt_path = path.parent / 'receipt.json'
        if receipt_path.is_symlink(): raise ValueError('Symlinked audio receipt is unsupported')
        receipt = json.loads(receipt_path.read_text())
        stamp = path.lstat()
        if not stat.S_ISREG(stamp.st_mode): raise ValueError('Cached audio is not a regular file')
        # ponytail: size/mtime reuse avoids rereading a whole book on every batch;
        # export and timeline check the complete audio hash before using a file.
        if full or stamp.st_size != receipt.get('audio_bytes') or stamp.st_mtime_ns != receipt.get('audio_mtime_ns'):
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'rb') as stream:
                before = os.fstat(stream.fileno())
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                after = os.fstat(stream.fileno())
            if identity(stamp) != identity(before) or identity(before) != identity(after) or actual != receipt['audio_sha256']:
                raise ValueError('Cached audio bytes changed')
        seconds = receipt['seconds']
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0: raise ValueError('Invalid cached duration')
        duration = inspect_wav(path) if full else seconds
        current = path.lstat()
        if identity(stamp) != identity(current) or not stat.S_ISREG(current.st_mode): raise ValueError('Cached audio changed while inspecting')
        return duration
    except (OSError, KeyError, ValueError, wave.Error, EOFError) as exc:
        raise ValueError('Audio cache is incomplete or changed; use pagecast_retry for only the affected passage') from exc


class Books:
    def __init__(self, root, settings=None):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.settings = settings or {}
        self.runtime_hashes = {}
        self.db_path = self.root / 'books.db'
        fd = os.open(self.db_path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0), 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('Book database must be a regular file')
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS books(id TEXT PRIMARY KEY,title TEXT NOT NULL,revision INTEGER NOT NULL,source_hash TEXT NOT NULL,created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS passages(book TEXT NOT NULL,id INTEGER NOT NULL,chapter INTEGER NOT NULL,chapter_title TEXT NOT NULL,paragraph INTEGER NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,quote_id TEXT,text TEXT NOT NULL,speaker TEXT NOT NULL,PRIMARY KEY(book,id));
              CREATE TABLE IF NOT EXISTS voices(book TEXT NOT NULL,speaker TEXT NOT NULL,spec TEXT NOT NULL,locked INTEGER NOT NULL,PRIMARY KEY(book,speaker));
              CREATE TABLE IF NOT EXISTS audio(book TEXT NOT NULL,passage INTEGER NOT NULL,signature TEXT NOT NULL,path TEXT NOT NULL,seconds REAL NOT NULL,PRIMARY KEY(book,passage));
              CREATE TABLE IF NOT EXISTS renders(book TEXT PRIMARY KEY,state TEXT NOT NULL,done INTEGER NOT NULL,total INTEGER NOT NULL,error TEXT,updated REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS paid_attempts(id TEXT PRIMARY KEY,book TEXT NOT NULL,passage INTEGER NOT NULL,signature TEXT NOT NULL,status TEXT NOT NULL,requested_units INTEGER NOT NULL,reported_units INTEGER,model TEXT NOT NULL,http_status INTEGER,retry_allowed INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=10); db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def folder(self, book_id):
        if not isinstance(book_id, str) or not re.fullmatch('[0-9a-f]{32}', book_id): raise ValueError('Invalid book ID')
        folder = self.root / book_id
        if not folder.is_dir() or folder.is_symlink(): raise ValueError('Unknown book')
        return folder

    @contextmanager
    def lock(self, book_id, name='edit'):
        with (self.folder(book_id) / (name + '.lock')).open('a') as handle:
            try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError('This book is busy; wait for the current operation') from None
            yield

    def import_book(self, title=None, text=None, source_path=None, allow_profile_books=False):
        if type(allow_profile_books) is not bool: raise ValueError('allow_profile_books must be boolean')
        if (text is None) == (source_path is None): raise ValueError('Provide exactly one of text or source_path')
        if source_path is not None:
            profile_data = self.root.parent if self.root.parent.name == 'plugin-data' else None
            source_title, chapters, source_hash = import_file(source_path, profile_data, allow_profile_books)
            title = title or source_title
        else:
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT: raise ValueError('Text must contain1–1000000 characters')
            chapters = [{'title': 'Chapter1', 'paragraphs': [p.strip() for p in text.splitlines() if p.strip()]}]
            source_hash = hashlib.sha256(text.encode()).hexdigest()
        title = title or 'Untitled'
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200 or any(ord(c) < 32 for c in title): raise ValueError('Title must contain1–200 printable characters')
        units = segment(chapters)
        identifier = uuid.uuid4().hex; folder = self.root / identifier; folder.mkdir(mode=0o700)
        (folder / 'cache').mkdir(); (folder / 'failures').mkdir()
        with self.db() as db:
            db.execute('INSERT INTO books VALUES(?,?,?,?,?)', (identifier, title, 1, source_hash, time.time()))
            db.executemany('INSERT INTO passages VALUES(?,?,?,?,?,?,?,?,?,?)',
                [(identifier, i, u['chapter'], u['chapter_title'], u['paragraph'], u['start'], u['end'], u['quote_id'], u['text'], 'Narrator') for i, u in enumerate(units)])
            db.execute('INSERT INTO voices VALUES(?,?,?,?)', (identifier, 'Narrator', json.dumps({'engine': 'flite', 'voice': 'rms'}), 0))
        return {'book_id': identifier, 'title': title, 'passages': len(units), 'chapters': len(chapters),
                'quoted_passages_using_narrator': sum(u['quote_id'] is not None for u in units), 'source_hash': source_hash}

    def _snapshot(self, book_id):
        self.folder(book_id)
        with self.db() as db:
            book = dict(db.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone())
            passages = [dict(r) for r in db.execute('SELECT * FROM passages WHERE book=? ORDER BY id', (book_id,))]
            voices = {r['speaker']: {**json.loads(r['spec']), 'locked': bool(r['locked'])} for r in db.execute('SELECT * FROM voices WHERE book=?', (book_id,))}
        return book, passages, voices

    def get(self, book_id, offset=0, limit=50):
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('Use a nonnegative offset and limit1–100')
        book, passages, voices = self._snapshot(book_id)
        with self.db() as db:
            render = db.execute('SELECT * FROM renders WHERE book=?', (book_id,)).fetchone()
        render = dict(render) if render else None
        if render and render['state'] == 'rendering':
            try:
                with self.lock(book_id, 'render'):
                    with self.db() as db: latest = dict(db.execute('SELECT * FROM renders WHERE book=?', (book_id,)).fetchone())
                    render = latest if latest['state'] != 'rendering' else {**latest, 'state': 'interrupted', 'error': 'No renderer owns the book; resume from the existing cache'}
            except RuntimeError:
                pass  # a renderer still owns the lock
        return {'book': book, 'voices': voices, 'passages': passages[offset:offset+limit], 'total': len(passages),
                'next_offset': offset + limit if offset + limit < len(passages) else None,
                'render': render, 'usage': self.usage(book_id)}

    def list_books(self):
        with self.db() as db: return {'books': [dict(r) for r in db.execute('SELECT * FROM books ORDER BY created DESC LIMIT 100')]}

    def assign(self, book_id, passage_ids, speaker):
        if not isinstance(speaker, str) or not 1 <= len(speaker.strip()) <= 80 or any(ord(c) < 32 for c in speaker): raise ValueError('Speaker must contain1–80 printable characters')
        if not isinstance(passage_ids, list) or not 1 <= len(passage_ids) <= 500 or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in passage_ids): raise ValueError('Select1–500 passage IDs')
        with self.lock(book_id), self.db() as db:
            existing = {r['id']: r['speaker'] for r in db.execute('SELECT id,speaker FROM passages WHERE book=?', (book_id,))}
            if any(i not in existing for i in passage_ids): raise ValueError('A passage does not belong to this book; no changes made')
            changed = [i for i in set(passage_ids) if existing[i] != speaker]
            if changed:
                narrator = db.execute('SELECT spec FROM voices WHERE book=? AND speaker=?', (book_id, 'Narrator')).fetchone()
                db.execute('INSERT OR IGNORE INTO voices VALUES(?,?,?,0)', (book_id, speaker, narrator['spec']))
                db.executemany('UPDATE passages SET speaker=? WHERE book=? AND id=?', [(speaker, book_id, i) for i in changed])
                db.execute('UPDATE books SET revision=revision+1 WHERE id=?', (book_id,))
                db.execute('UPDATE renders SET state=?,updated=? WHERE book=?', ('needs_render', time.time(), book_id))
        return {'changed_passages': changed, 'speaker': speaker}

    def set_voice(self, book_id, speaker, engine='flite', voice=None, reference_audio='', reference_text='', locked=True, replace_locked=False):
        if not isinstance(locked, bool) or not isinstance(replace_locked, bool): raise ValueError('Lock flags must be booleans')
        if not isinstance(speaker, str) or not 1 <= len(speaker.strip()) <= 80: raise ValueError('Choose a speaker name')
        if not isinstance(reference_audio, str) or not isinstance(reference_text, str): raise ValueError('Reference path and transcript must be strings')
        if voice is None: voice = 'rms' if engine == 'flite' else 'Ashley' if engine == 'inworld' else 'default'
        spec = {'engine': engine, 'voice': voice}
        if engine == 'flite':
            if voice not in FLITE_VOICES: raise ValueError('Choose a built-in Flite voice: ' + ', '.join(FLITE_VOICES))
            if reference_audio or reference_text: raise ValueError('Voice references apply only to Higgs')
        elif engine == 'higgs':
            if not isinstance(voice, str) or not 1 <= len(voice) <= 80 or not isinstance(reference_text, str) or len(reference_text) > 2000: raise ValueError('Invalid Higgs voice or reference transcript')
            spec.update(reference_audio=reference_audio, reference_text=reference_text)
            self._voice(spec)  # validates reference before accepting the cast change
        elif engine == 'inworld':
            inworld.valid_voice(voice)
            if reference_audio or reference_text: raise ValueError('For Inworld, select an existing voice ID; local references are supported by Higgs only')
        else: raise ValueError('Choose flite, higgs or inworld')
        with self.lock(book_id), self.db() as db:
            row = db.execute('SELECT * FROM voices WHERE book=? AND speaker=?', (book_id, speaker)).fetchone()
            if row is None: raise ValueError('Assign a passage to this speaker first')
            previous = json.loads(row['spec'])
            if row['locked'] and previous != spec and not replace_locked: raise ValueError('Voice is locked. Replace it only for an explicit user-requested change')
            if previous != spec or bool(row['locked']) != locked:
                db.execute('UPDATE voices SET spec=?,locked=? WHERE book=? AND speaker=?', (json.dumps(spec), int(locked), book_id, speaker))
                db.execute('UPDATE books SET revision=revision+1 WHERE id=?', (book_id,))
                db.execute('UPDATE renders SET state=?,updated=? WHERE book=?', ('needs_render', time.time(), book_id))
            count = db.execute('SELECT COUNT(*) FROM passages WHERE book=? AND speaker=?', (book_id, speaker)).fetchone()[0]
        return {'speaker': speaker, 'voice': spec, 'locked': locked, 'affected_passages': count if previous != spec else 0}

    def edit(self, book_id, passage_id, text):
        if isinstance(passage_id, bool) or not isinstance(passage_id, int) or not isinstance(text, str) or not text.strip() or len(text) > 350 or len(text.split()) > 60:
            raise ValueError('Select a passage and provide1–350 characters, at most60 words')
        with self.lock(book_id), self.db() as db:
            row = db.execute('SELECT text FROM passages WHERE book=? AND id=?', (book_id, passage_id)).fetchone()
            if row is None: raise ValueError('Passage does not belong to this book')
            if row['text'] != text:
                db.execute('UPDATE passages SET text=? WHERE book=? AND id=?', (text, book_id, passage_id))
                db.execute('UPDATE books SET revision=revision+1 WHERE id=?', (book_id,))
                db.execute('UPDATE renders SET state=?,updated=? WHERE book=?', ('needs_render', time.time(), book_id))
        return {'passage_id': passage_id, 'changed': row['text'] != text, 'source_offsets': 'Original source coordinates retained; edited text can differ in length.'}

    def _voice(self, spec):
        value = {k: v for k, v in spec.items() if k != 'locked'}
        if value['engine'] == 'flite':
            binary = shutil.which('flite')
            if not binary: raise ValueError('Install Flite for offline voices, or explicitly select Higgs/Inworld')
            stamp = Path(binary).stat()
            key = (binary, stamp.st_size, stamp.st_mtime_ns)
            if key not in self.runtime_hashes:
                with open(binary, 'rb') as stream: self.runtime_hashes[key] = hashlib.file_digest(stream, 'sha256').hexdigest()
            value['runtime_sha256'] = self.runtime_hashes[key]
        elif value['engine'] == 'inworld':
            model = self.settings.get('inworld_model', 'inworld-tts-2')
            if model not in inworld.MODELS: raise ValueError('Choose a supported Inworld TTS-2 model')
            value.update(model=model, delivery_mode='BALANCED', sample_rate=48000, request_format='inworld-unary-linear16-v1')
        else:
            value.update(endpoint=self.settings.get('higgs_url', 'http://localhost:8000'), model=self.settings.get('higgs_model', 'bosonai/higgs-tts-3-4b'), revision=self.settings.get('higgs_revision', ''))
            path = value.get('reference_audio')
            if path:
                ref = resolve_reference(path, self.root)
                if not ref.is_file() or ref.suffix.lower() != '.wav' or ref.stat().st_size > 5 * 1024 * 1024: raise ValueError('Higgs reference must be a local WAV of at most5 MiB')
                data = ref.read_bytes()
                if data[:4] != b'RIFF' or data[8:12] != b'WAVE': raise ValueError('Voice reference is not a WAV')
                info = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(ref)]))
                duration = float(info['format']['duration'])
                if not math.isfinite(duration) or not 0 < duration <= 30 or not any(s['codec_type'] == 'audio' for s in info['streams']):
                    raise ValueError('Voice reference must contain audio and be at most30 seconds')
                value['reference_hash'] = hashlib.sha256(data).hexdigest()
                # An immutable data URI binds generation to these exact reference
                # bytes, even if the source file is edited during the render.
                value['reference_data'] = 'data:audio/wav;base64,' + base64.b64encode(data).decode()
        return value

    def plan(self, book_id):
        book, passages, cast = self._snapshot(book_id)
        voices = {name: self._voice(cast[name]) for name in {p['speaker'] for p in passages}}
        for passage in passages:
            voice = voices[passage['speaker']]
            passage['signature'] = digest(['pcm24k-v1', passage['text'], {k: v for k, v in voice.items() if k not in ('reference_data', 'reference_audio')}])
            passage['audio_path'] = str(self.folder(book_id) / 'cache' / passage['signature'] / 'audio.wav')
        return book, passages, voices

    def _state(self, book_id, state, done, total, error=None):
        with self.db() as db:
            db.execute('INSERT INTO renders VALUES(?,?,?,?,?,?) ON CONFLICT(book) DO UPDATE SET state=excluded.state,done=excluded.done,total=excluded.total,error=excluded.error,updated=excluded.updated',
                       (book_id, state, done, total, error, time.time()))

    def usage(self, book_id):
        self.folder(book_id)
        with self.db() as db:
            row = db.execute('''SELECT COUNT(*) requests, COALESCE(SUM(reported_units),0) reported_characters,
                COALESCE(SUM(CASE WHEN reported_units IS NULL THEN requested_units ELSE 0 END),0) input_units_without_reported_usage,
                COALESCE(SUM(CASE WHEN status IN ('pending','unknown') OR (status IN ('received','audio_invalid') AND reported_units IS NULL) THEN 1 ELSE 0 END),0) unknown_outcomes
                FROM paid_attempts WHERE book=?''', (book_id,)).fetchone()
        return {**dict(row), 'provider': 'inworld', 'notice': 'Provider-reported characters are usage, not a dollar charge. Unreported input units are estimates; check provider billing.'}

    def _inworld_audio(self, book_id, passage, voice):
        with self.db() as db:
            prior = db.execute("SELECT id FROM paid_attempts WHERE book=? AND signature=? AND retry_allowed=0 AND status IN ('pending','unknown','received','audio_invalid') LIMIT 1",
                               (book_id, passage['signature'])).fetchone()
        if prior:
            raise RuntimeError('A previous Inworld attempt has no usable cache and may have been billed. Review usage and explicitly use pagecast_retry before sending another paid request')
        attempt = uuid.uuid4().hex
        def observe(status, data):
            with self.db() as db:
                db.execute('''INSERT INTO paid_attempts(id,book,passage,signature,status,requested_units,reported_units,model,http_status,created)
                    VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                    reported_units=COALESCE(excluded.reported_units,paid_attempts.reported_units),
                    http_status=COALESCE(excluded.http_status,paid_attempts.http_status),model=excluded.model''',
                    (attempt, book_id, passage['id'], passage['signature'], status, inworld.units(passage['text']), data.get('reported_units'), data.get('model_id', voice['model']), data.get('http_status'), time.time()))
        audio, _ = inworld.synthesize(passage['text'], voice['voice'], voice['model'], observe)
        return audio

    def render(self, book_id, max_segments=20):
        if isinstance(max_segments, bool) or not isinstance(max_segments, int) or not 1 <= max_segments <= 100: raise ValueError('Render1–100 passages per bounded call')
        if not shutil.which('ffmpeg'): raise ValueError('FFmpeg is required for normalized audio')
        with self.lock(book_id, 'render'):
            folder = self.folder(book_id); (folder / 'cancel').unlink(missing_ok=True)
            book, passages, voices = self.plan(book_id)
            done, generated, reused, recovered = 0, 0, 0, 0
            staged = {}
            for candidate in (folder / 'cache').glob('.staging-*'):
                try:
                    receipt = json.loads((candidate / 'receipt.json').read_text())
                    if receipt.get('source_revision') == book['revision'] and not candidate.is_symlink():
                        staged.setdefault(receipt['signature'], candidate)
                except (OSError, ValueError, KeyError):
                    pass  # incomplete work is preserved, not represented as accepted audio
            self._state(book_id, 'rendering', 0, len(passages))
            try:
                for passage in passages:
                    if (folder / 'cancel').exists(): self._state(book_id, 'cancelled', done, len(passages)); break
                    with self.db() as db: revision = db.execute('SELECT revision FROM books WHERE id=?', (book_id,)).fetchone()[0]
                    if revision != book['revision']: self._state(book_id, 'stale', done, len(passages), 'Book/cast changed; resume to use the current revision'); break
                    target = Path(passage['audio_path'])
                    candidate = staged.get(passage['signature'])
                    if not target.parent.exists() and candidate is not None and candidate.exists():
                        verify_cache(candidate / 'audio.wav')
                        candidate.rename(target.parent)
                        recovered += 1
                    if target.exists():
                        duration = verify_cache(target, full=False); reused += 1
                    else:
                        if target.parent.exists(): raise ValueError('Incomplete audio cache entry; review or retry this passage explicitly')
                        if generated >= max_segments: self._state(book_id, 'partial', done, len(passages)); break
                        raw = folder / 'failures' / (uuid.uuid4().hex + '.wav')
                        voice = voices[passage['speaker']]
                        contract = {'passage_id': passage['id'], 'signature': passage['signature'], 'source_revision': book['revision'], 'text': passage['text'],
                                    'speaker': passage['speaker'], 'engine': voice['engine'], 'voice': {k: v for k, v in voice.items() if k != 'reference_data'},
                                    'acceptance': 'nonempty normalized WAV, bounded duration; semantic/listening review separate'}
                        raw.with_suffix('.json').write_text(json.dumps(contract, indent=2))
                        if voice['engine'] == 'flite':
                            script = raw.with_suffix('.txt'); script.write_text(passage['text']); script.chmod(0o600)
                            try: run(['flite', '-voice', voice['voice'], '-f', str(script), '-o', str(raw)], timeout=30)
                            finally: script.unlink(missing_ok=True)
                        elif voice['engine'] == 'higgs':
                            raw.write_bytes(synthesize(voice['endpoint'], voice['model'], passage['text'], voice['voice'], voice.get('reference_data', ''), voice.get('reference_text', '')))
                        else:
                            raw.write_bytes(self._inworld_audio(book_id, passage, voice))
                        staging = folder / 'cache' / ('.staging-' + uuid.uuid4().hex); staging.mkdir(mode=0o700)
                        temporary = staging / 'audio.wav'
                        run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-i', str(raw), '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', str(temporary)])
                        duration = inspect_wav(temporary)
                        if duration > max(15, len(passage['text'].split()) * .9):
                            temporary.unlink(missing_ok=True)
                            raise RuntimeError(f'Passage {passage["id"]} audio is unexpectedly long; failed take retained for review')
                        with temporary.open('rb') as data: contract['audio_sha256'] = hashlib.file_digest(data, 'sha256').hexdigest()
                        contract['seconds'] = duration
                        contract['audio_bytes'] = temporary.stat().st_size
                        contract['audio_mtime_ns'] = temporary.stat().st_mtime_ns
                        (staging / 'receipt.json').write_text(json.dumps(contract, indent=2))
                        staging.rename(target.parent)  # audio and receipt become visible atomically
                        raw.unlink(); raw.with_suffix('.json').unlink()
                        generated += 1
                    with self.lock(book_id), self.db() as db:
                        current = db.execute('SELECT revision FROM books WHERE id=?', (book_id,)).fetchone()[0]
                        if current != book['revision']:
                            self._state(book_id, 'stale', done, len(passages), 'Book/cast changed during synthesis; cached audio retained')
                            break
                        db.execute('INSERT INTO audio VALUES(?,?,?,?,?) ON CONFLICT(book,passage) DO UPDATE SET signature=excluded.signature,path=excluded.path,seconds=excluded.seconds',
                                   (book_id, passage['id'], passage['signature'], str(target), duration))
                    done += 1; self._state(book_id, 'rendering', done, len(passages))
                else: self._state(book_id, 'complete', done, len(passages))
            except Exception as exc:
                self._state(book_id, 'failed', done, len(passages), str(exc))
                return {'state': 'failed', 'generated': generated, 'reused': reused, 'error': str(exc)}
        return {**self.get(book_id, limit=1)['render'], 'generated': generated, 'reused': reused, 'recovered': recovered}

    def cancel(self, book_id):
        (self.folder(book_id) / 'cancel').touch(mode=0o600)
        return {'cancel_requested': True, 'notice': 'Cancellation takes effect between passages; the current bounded speech call may finish first.'}

    def preview(self, book_id, passage_id):
        if isinstance(passage_id, bool) or not isinstance(passage_id, int): raise ValueError('Select a passage ID')
        _, passages, _ = self.plan(book_id)
        passage = next((p for p in passages if p['id'] == passage_id), None)
        if passage is None: raise ValueError('Unknown passage')
        path = Path(passage['audio_path'])
        if not path.exists(): raise ValueError('Render this passage with its current voice before previewing')
        duration = verify_cache(path)
        if not shutil.which('mpv'): raise ValueError('Install mpv to preview on the Hermes host')
        process = subprocess.Popen(['mpv', '--no-config', '--load-scripts=no', '--ytdl=no', '--no-video', '--audio-display=no',
            '--terminal=no', '--input-terminal=no', '--force-media-title=' + passage['speaker'], str(path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, env=process_env())
        threading.Thread(target=process.wait, daemon=True).start()
        return {'state': 'launched', 'passage_id': passage_id, 'seconds': duration,
                'notice': 'Audio preview launched on the Hermes host. Listening quality is not automatically verified.'}

    def retry(self, book_id, passage_ids):
        if not isinstance(passage_ids, list) or not passage_ids or len(passage_ids) > 100 or any(isinstance(i, bool) or not isinstance(i, int) for i in passage_ids):
            raise ValueError('Select1–100 passage IDs for an explicit new take')
        with self.lock(book_id, 'render'), self.lock(book_id):
            _, passages, _ = self.plan(book_id)
            selected = {p['id']: p for p in passages if p['id'] in passage_ids}
            if len(selected) != len(set(passage_ids)): raise ValueError('Passage does not belong to this book')
            signatures = {p['signature'] for p in selected.values()}
            archive = self.folder(book_id) / 'archive'; archive.mkdir(exist_ok=True, mode=0o700)
            retained = []
            for signature in signatures:
                cache = self.folder(book_id) / 'cache' / signature
                if cache.exists():
                    destination = archive / (signature + '-' + uuid.uuid4().hex)
                    cache.rename(destination); retained.append(str(destination))
            with self.db() as db:
                db.executemany('DELETE FROM audio WHERE book=? AND signature=?', [(book_id, s) for s in signatures])
                db.executemany('UPDATE paid_attempts SET retry_allowed=1 WHERE book=? AND signature=?', [(book_id, s) for s in signatures])
                db.execute('UPDATE books SET revision=revision+1 WHERE id=?', (book_id,))
                db.execute('UPDATE renders SET state=?,updated=? WHERE book=?', ('needs_render', time.time(), book_id))
            return {'affected_passages': [p['id'] for p in passages if p['signature'] in signatures], 'previous_takes_preserved': retained}

    def timeline(self, book_id, offset=0, limit=50, include_text=False):
        if type(include_text) is not bool: raise ValueError('include_text must be boolean')
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= (100 if include_text else 1000):
            raise ValueError('Use nonnegative offset and limit 1–100 with text or 1–1000 without text')
        with self.lock(book_id):
            book, passages, _ = self.plan(book_id)
            if offset > len(passages): raise ValueError('Timeline offset exceeds passage count')
            end = min(len(passages), offset + limit)
            elapsed, result, checked = 0.0, [], {}
            for index, passage in enumerate(passages[:end]):
                path = passage['audio_path']
                if path not in checked: checked[path] = verify_cache(path)
                duration = checked[path]
                if index >= offset:
                    row = {'passage_id': passage['id'], 'chapter': passage['chapter'], 'paragraph': passage['paragraph'],
                           'speaker': passage['speaker'], 'start_seconds': elapsed, 'end_seconds': elapsed + duration}
                    if include_text: row['text'] = passage['text']
                    result.append(row)
                elapsed += duration
            return {'book_id': book_id, 'book_revision': book['revision'], 'source_sha256': book['source_hash'], 'passages': result, 'total': len(passages),
                    'next_offset': end if end < len(passages) else None, 'verified_prefix_passages': end,
                    'notice': 'Times sum verified cached WAV durations in passage order; only the requested prefix was checked. The source hash identifies the initial import, not later edits. Export encoding and edits can change playback timing. Optional passage text is untrusted and may be sensitive.'}

    def export(self, book_id, format='m4b'):
        if format not in ('wav', 'm4b'): raise ValueError('Choose wav or m4b')
        with self.lock(book_id):
            book, passages, voices = self.plan(book_id)
            missing = [p['id'] for p in passages if not Path(p['audio_path']).exists()]
            if missing: raise ValueError(f'{len(missing)} passages need rendering for the current cast/text; export refused')
            durations = [verify_cache(p['audio_path']) for p in passages]
            if format == 'wav' and sum(durations) * 48000 > 0xffffffff - 36: raise ValueError('Export exceeds the WAV4GiB format limit; use M4B')
            folder = self.folder(book_id); output = folder / ('book-' + uuid.uuid4().hex + '.' + format)
            temporary = output.with_name(output.stem + '.part.' + format)
            chapter_marks, elapsed = [], 0.0
            for passage, duration in zip(passages, durations):
                if not chapter_marks or chapter_marks[-1]['chapter'] != passage['chapter']:
                    chapter_marks.append({'chapter': passage['chapter'], 'title': passage['chapter_title'], 'start': elapsed, 'end': elapsed + duration})
                else: chapter_marks[-1]['end'] = elapsed + duration
                elapsed += duration
            manifest = output.with_suffix('.concat.txt'); metadata = output.with_suffix('.metadata.txt')
            try:
                actual_duration = sum(durations)
                if format == 'wav':
                    with wave.open(str(temporary), 'wb') as wav:
                        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
                        for passage in passages:
                            with wave.open(passage['audio_path'], 'rb') as source:
                                while data := source.readframes(24000): wav.writeframesraw(data)
                    inspect_wav(temporary)
                else:
                    if '\n' in str(folder): raise ValueError('Newlines in the storage directory are unsupported by audio export')
                    manifest.write_text(''.join("file '" + p['audio_path'].replace("'", "'\\''") + "'\n" for p in passages))
                    def escape(text): return ''.join('\\' + c if c in '\\=;#\n' else c for c in text)
                    meta = ';FFMETADATA1\ntitle=' + escape(book['title']) + '\n'
                    for chapter in chapter_marks:
                        meta += f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(chapter["start"]*1000)}\nEND={round(chapter["end"]*1000)}\ntitle={escape(chapter["title"])}\n'
                    metadata.write_text(meta)
                    run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'concat', '-safe', '0', '-i', str(manifest), '-i', str(metadata),
                         '-map', '0:a:0', '-map_metadata', '1', '-map_chapters', '1', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(temporary)], timeout=300)
                    run(['ffmpeg', '-v', 'error', '-xerror', '-nostdin', '-i', str(temporary), '-f', 'null', '-'], timeout=180)
                    info = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_chapters', '-of', 'json', str(temporary)]))
                    actual_duration = float(info['format']['duration'])
                    if len(info.get('chapters', [])) != len(chapter_marks): raise RuntimeError('Chapter metadata validation failed')
                temporary.replace(output)
            except Exception:
                temporary.unlink(missing_ok=True); raise
            finally:
                manifest.unlink(missing_ok=True); metadata.unlink(missing_ok=True)
            receipt = {'path': str(output), 'title': book['title'], 'book_revision': book['revision'],
                       'seconds': actual_duration, 'passages': len(passages), 'source_hash': book['source_hash'], 'chapters': chapter_marks, 'format': format}
            if any(voices[p['speaker']].get('engine') == 'higgs' for p in passages):
                receipt['credit'] = "This audio was created with Boson AI's Higgs Audio — https://www.boson.ai/higgs-audio"
                output.with_suffix('.credit.txt').write_text(receipt['credit'] + '\n')
            output.with_suffix('.json').write_text(json.dumps(receipt, indent=2))
            return receipt

"""Audiogram clips: a span of one rendered chapter as a short captioned MP4 plus an SRT.

Pure helpers (span selection, caption timing, SRT/ASS text) and one FFmpeg call. Caption text goes
to a subtitle file, never into an FFmpeg filter string, so quotes, colons, percent signs,
backslashes and non-Latin text cannot break the command. Nothing is uploaded.
"""
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .process_env import process_env
from .readalong import word_spans

MIN_SECONDS, MAX_SECONDS, TARGET = 5.0, 180.0, (15.0, 90.0)
FPS = 25
WORD_JOINER = '\u2060'   # zero-width: keeps a literal backslash from forming an ASS code such as backslash-N
BACKGROUND = '0x12161c'
IMAGE_SUFFIXES = ('.jpg', '.jpeg', '.png', '.webp')
# Box and caption geometry per shape. cover/wave are (x, y, w, h); text is (alignment, left, right, top margin, font size).
SHAPES = {
    'vertical': {'size': (1080, 1920), 'cover': (140, 300, 800, 800), 'wave': (90, 1580, 900, 160), 'chars': 70,
                 'title': (8, 80, 80, 80, 52), 'caption': (8, 90, 90, 1210, 64), 'speaker': (8, 90, 90, 1140, 42)},
    'square': {'size': (1080, 1080), 'cover': (390, 130, 300, 300), 'wave': (70, 900, 940, 120), 'chars': 70,
               'title': (8, 60, 60, 30, 40), 'caption': (8, 70, 70, 500, 48), 'speaker': (8, 70, 70, 450, 34)},
    'wide': {'size': (1920, 1080), 'cover': (80, 140, 760, 760), 'wave': (900, 830, 940, 140), 'chars': 80,
             'title': (7, 900, 80, 90, 54), 'caption': (7, 900, 80, 400, 62), 'speaker': (7, 900, 80, 340, 40)},
}


def tools(need_waveform=False):
    """Locate the user's FFmpeg and say plainly what is missing."""
    missing = [name for name in ('ffmpeg', 'ffprobe') if not shutil.which(name)]
    if missing:
        raise ValueError('Audiograms need FFmpeg: ' + ' and '.join(missing) + ' not found on PATH. Install FFmpeg (with libass and libx264) and try again; nothing was written.')
    try:
        listing = subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True, timeout=30, env=process_env()).stdout
        encoders = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True, timeout=30, env=process_env()).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError('FFmpeg could not be run: ' + str(exc)[:200]) from exc
    filters = {line.split()[1] for line in listing.splitlines() if len(line.split()) > 2 and line.startswith(' ')}
    lacking = [f for f in ('ass', 'overlay', 'gblur', 'colorkey', 'afade') + (('showwaves',) if need_waveform else ()) if f not in filters]
    if 'libx264' not in encoders: lacking.append('libx264 encoder')
    if lacking: raise ValueError('This FFmpeg build lacks ' + ', '.join(lacking) + ' (needs libass for captions and libx264 for video); nothing was written.')


def normal(text):
    text = text.translate({0x2018: "'", 0x2019: "'", 0x201c: '"', 0x201d: '"'})
    return re.sub(r'\s+', ' ', text).strip().casefold()


def select(rows, start, end):
    """rows: one chapter's passages as dicts id/start/end/text (seconds relative to the chapter).
    start and end are (kind, value). Returns (first_index, last_index), snapped outward to whole passages."""
    ids = [r['id'] for r in rows]
    total = rows[-1]['end']
    def need_number(value, label):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0: raise ValueError(label + ' must be a number of seconds from the start of the chapter, 0 or more')
        return float(value)
    def words(value, label):
        if not isinstance(value, str) or not normal(value): raise ValueError(label + ' must be some words from the passage')
        return normal(value)
    kind, value = start
    if kind == 'first_passage_id':
        if value not in ids: raise ValueError(f'first_passage_id {value} is not in this chapter (passage ids {ids[0]} to {ids[-1]})')
        first = ids.index(value)
    elif kind == 'start_seconds':
        value = need_number(value, 'start_seconds')
        if value >= total: raise ValueError(f'start_seconds {value:g} is after the end of the chapter ({total:.1f} s)')
        first = max(i for i, r in enumerate(rows) if r['start'] <= value + 1e-9)
    else:
        phrase = words(value, 'first_words')
        hits = [i for i, r in enumerate(rows) if phrase in normal(r['text'])]
        if not hits: raise ValueError('first_words were not found in this chapter; read the sentences with pagecast_timeline (chapter, include_text) and copy exact words')
        first = hits[0]
    kind, value = end
    if kind == 'last_passage_id':
        if value not in ids: raise ValueError(f'last_passage_id {value} is not in this chapter (passage ids {ids[0]} to {ids[-1]})')
        last = ids.index(value)
    elif kind == 'end_seconds':
        value = need_number(value, 'end_seconds')
        if value > total + .01: raise ValueError(f'end_seconds {value:g} is after the end of the chapter ({total:.1f} s)')
        last = min((i for i, r in enumerate(rows) if r['end'] >= value - 1e-9), default=len(rows) - 1)
    else:
        phrase = words(value, 'last_words')
        hits = [i for i, r in enumerate(rows) if i >= first and phrase in normal(r['text'])]
        if not hits: raise ValueError('last_words were not found at or after the first passage in this chapter')
        last = hits[0]
    if last < first: raise ValueError('The end comes before the start; choose a range that moves forward through the chapter')
    return first, last


def split_phrases(text, limit):
    """Character ranges of caption pieces of at most `limit` characters, breaking after punctuation where possible."""
    pieces, begin, end = [], None, None
    def flush():
        nonlocal begin, end
        if begin is not None: pieces.append((begin, end))
        begin = end = None
    for match in re.finditer(r'\S+', text):
        a, b = match.span()
        while b - a > limit:   # no spaces to break on (for example CJK text)
            flush(); pieces.append((a, a + limit)); a += limit
        if begin is not None and b - begin > limit: flush()
        if begin is None: begin = a
        end = b
        if end - begin >= limit * .5 and re.search(r'[.!?;:,\u3002\uff01\uff1f\u2014]["\')\u201d\u2019]*$', match.group()): flush()
    flush()
    merged = []
    for piece in pieces:   # a short tail would flash by: join it to the piece before it
        if merged and piece[1] - piece[0] < limit * .35 and piece[1] - merged[-1][0] <= limit * 1.3: merged[-1] = (merged[-1][0], piece[1])
        else: merged.append(piece)
    return merged


def u16(text, index):
    return len(text[:index].encode('utf-16-le')) // 2


def passage_cues(text, duration, offset, metadata, limit):
    """Timed caption pieces of one passage. Times are seconds in the clip. kind is word or estimated."""
    pieces = split_phrases(text, limit)
    if not pieces: return []
    spans = word_spans(text, metadata, duration)
    out = []
    for a, b in pieces:
        inside = [s for s in spans if s['from'] >= u16(text, a) and s['to'] <= u16(text, b)]
        if inside: out.append([inside[0]['start'], inside[-1]['end'], 'word', text[a:b]])
        else: out.append([duration * a / len(text), duration * b / len(text), 'estimated', text[a:b]])
    out[0][0] = 0.0
    for i, cue in enumerate(out):
        cue[1] = out[i + 1][0] if i + 1 < len(out) else duration   # each caption holds until the next one
        if cue[1] <= cue[0]: cue[1] = min(duration, cue[0] + .05)
    return [{'start': offset + s, 'end': offset + e, 'kind': k, 'text': t} for s, e, k, t in out]


def timestamp(seconds, srt):
    ms = round(max(0.0, seconds) * 1000)
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}' if srt else f'{h}:{m:02d}:{s:02d}.{ms // 10:02d}'


def srt_text(cues):
    return ''.join(f"{i}\n{timestamp(c['start'], True)} --> {timestamp(c['end'], True)}\n{(c['speaker'] + ': ' if c.get('speaker') else '') + c['text']}\n\n" for i, c in enumerate(cues, 1))


def ass_escape(text):
    text = text.replace(WORD_JOINER, '').replace('\r', '')
    text = text.replace('\\', '\\' + WORD_JOINER).replace('{', '\\{').replace('}', '\\}')   # a lone backslash before N, n or h would be a code
    return re.sub(r'\s*\n\s*', '\\\\N', text).strip()


def ass_text(shape, title, chapter, cues, duration):
    layout = SHAPES[shape]; w, h = layout['size']
    def style(name, spec, colour, bold=0):
        an, left, right, top, size = spec
        return f'Style: {name},Sans,{size},{colour},&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,100,100,0,0,1,{max(2, size // 16)},1,{an},{left},{right},{top},1\n'
    head = ('[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n' f'PlayResX: {w}\nPlayResY: {h}\n\n'
            '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
            + style('Title', layout['title'], '&H00FFFFFF', 1) + style('Caption', layout['caption'], '&H00FFFFFF', 1) + style('Speaker', layout['speaker'], '&H0064C8FF', 1)
            + '\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
    small = max(26, layout['title'][4] * 2 // 3)
    shown = (title[:117] + '...') if len(title) > 120 else title
    lines = [f"Dialogue: 0,{timestamp(0, False)},{timestamp(duration, False)},Title,,0,0,0,,{ass_escape(shown)}\\N{{\\fs{small}\\b0\\c&H00C8C8C8&}}{ass_escape(chapter[:100])}\n"]
    for c in cues:
        span = f"{timestamp(c['start'], False)},{timestamp(c['end'], False)}"
        if c.get('speaker'): lines.append(f"Dialogue: 0,{span},Speaker,,0,0,0,,{ass_escape(c['speaker'][:60])}\n")
        lines.append(f"Dialogue: 1,{span},Caption,,0,0,0,,{ass_escape(c['text'])}\n")
    return head + ''.join(lines)


def check_cover(path):
    path = Path(path)
    if path.suffix.lower() not in IMAGE_SUFFIXES: raise ValueError('cover_path must be a JPG, PNG or WebP image')
    if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024: raise ValueError('cover_path must be an image file of at most 20 MB')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', str(path)], capture_output=True, text=True, timeout=30, env=process_env())
    try: size = json.loads(probe.stdout)['streams'][0]
    except (ValueError, KeyError, IndexError): raise ValueError('cover_path is not a readable image') from None
    if probe.returncode or min(size['width'], size['height']) < 16: raise ValueError('cover_path is not a readable image')


def render(shape, wavs, duration, cues, title, chapter, output, cover=None, waveform=False):
    """Write output (MP4) from the audio files. Captions go through a subtitle file in a private work folder."""
    layout = SHAPES[shape]; w, h = layout['size']
    fade_in, fade_out = min(.25, duration / 8), min(.5, duration / 6)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.work-') as work:
        work = Path(work)
        (work / 'captions.ass').write_text(ass_text(shape, title, chapter, cues, duration), encoding='utf-8')
        if any(c in str(p) for p in wavs for c in '\n\r'): raise ValueError('Newlines in audio paths are unsupported')
        manifest = ''.join("file '" + Path(p).as_posix().replace("'", "'\\''") + "'\n" for p in wavs)
        (work / 'audio.txt').write_text(manifest, encoding='utf-8', newline='\n')
        cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-y', '-f', 'concat', '-safe', '0', '-i', 'audio.txt']
        if cover: cmd += ['-loop', '1', '-framerate', str(FPS), '-t', f'{duration:.3f}', '-i', str(Path(cover).resolve())]
        else: cmd += ['-f', 'lavfi', '-i', f'color=c={BACKGROUND}:s={w}x{h}:r={FPS}:d={duration:.3f}']
        cx, cy, cw, ch = layout['cover']
        graph = [f'[0:a]afade=t=in:st=0:d={fade_in:.3f},afade=t=out:st={max(0, duration - fade_out):.3f}:d={fade_out:.3f},aresample=44100,aformat=channel_layouts=stereo' + (',asplit=2[aout][aw]' if waveform else '[aout]')]
        if cover:
            graph.append(f'[1:v]format=rgb24,split=2[c1][c2];[c1]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=40,eq=brightness=-0.35:saturation=0.8[bg];'
                         f'[c2]scale={cw}:{ch}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay={cx}+({cw}-w)/2:{cy}+({ch}-h)/2[v0]')
        else: graph.append('[1:v]null[v0]')
        if waveform:
            wx, wy, ww, wh = layout['wave']
            graph.append(f'[aw]aformat=channel_layouts=mono,volume=12dB,showwaves=s={ww}x{wh}:mode=cline:scale=sqrt:draw=full:rate={FPS}:colors=white,format=rgba,colorkey=0x000000:0.1:0.2[wv];[v0][wv]overlay={wx}:{wy}[v1]')
        else: graph.append('[v0]null[v1]')
        graph.append('[v1]ass=captions.ass,format=yuv420p[vout]')
        part = output.with_name(output.stem + '.part.mp4')
        cmd += ['-filter_complex', ';'.join(graph), '-map', '[vout]', '-map', '[aout]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-r', str(FPS), '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '128k', '-t', f'{duration:.3f}', '-movflags', '+faststart', str(part)]
        try:
            done = subprocess.run(cmd, cwd=work, capture_output=True, text=True, env=process_env())   # no time limit: encoding time depends on the machine
            if done.returncode: raise RuntimeError('ffmpeg failed: ' + done.stderr[-600:])
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(part)], capture_output=True, text=True, timeout=60, env=process_env())
            info = json.loads(probe.stdout); video = next(s for s in info['streams'] if s['codec_type'] == 'video'); audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
            if (video['width'], video['height'], video['pix_fmt'], video['codec_name'], audio['codec_name']) != (w, h, 'yuv420p', 'h264', 'aac'): raise RuntimeError('Audiogram validation failed: unexpected video or audio format')
            seconds = float(info['format']['duration'])
            part.replace(output)
        finally:
            part.unlink(missing_ok=True)
    return seconds

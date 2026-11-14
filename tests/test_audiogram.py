"""pagecast_audiogram: real FFmpeg renders of a small generated chapter with hand-made timing data."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch

from test_pagecast import package, ROOT
from pagecast_test import audiogram as clip
from pagecast_test.books import Books

LINES = ['The first sentence is spoken here.', 'A second sentence follows it closely.', 'Third comes the quiet middle part.', 'Then the fourth sentence arrives.',
         'Fifth is where the story turns.', 'Sixth carries the hidden ending.', 'Seventh closes the chapter softly.', 'Eighth is the last line.']
SECONDS = [6, 7, 5, 8, 6, 7, 5, 6]
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def tone(path, seconds, hertz=330, silent=False):
    frames = int(seconds * 24000)
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        if silent: wav.writeframes(bytes(frames * 2))
        else: wav.writeframes(b''.join(struct.pack('<h', int(9000 * math.sin(2 * math.pi * hertz * i / 24000))) for i in range(frames)))


def alignment(text, seconds):
    words = text.split()
    step = seconds / len(words)
    return {'timestamp_info': {'wordAlignment': {'words': words, 'wordStartTimeSeconds': [i * step for i in range(len(words))], 'wordEndTimeSeconds': [(i + 1) * step - .05 for i in range(len(words))]}}}


def produce(books, book_id, seconds, timed=(), silent=False):
    """Write the cache entries pagecast_render would leave: audio.wav plus receipt.json (hash, duration, optional word timing)."""
    _, passages, _ = books.plan(book_id)
    for passage, length in zip(passages, seconds):
        target = Path(passage['audio_path']); target.parent.mkdir(parents=True, exist_ok=True)
        tone(target, length, 300 + 40 * passage['id'], silent)
        receipt = {'seconds': length, 'audio_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'audio_bytes': target.stat().st_size,
                   'audio_mtime_ns': target.stat().st_mtime_ns, 'provider_metadata': alignment(passage['text'], length) if passage['id'] in timed else {}}
        (target.parent / 'receipt.json').write_text(json.dumps(receipt))
    return passages


def probe(path):
    info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, text=True, check=True).stdout)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video'); audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    return video, audio, float(info['format']['duration'])


def frame_stats(path, at):
    """Mean luma of the picture at a time: a cheap way to see that something besides the background was drawn."""
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(path), '-frames:v', '1', '-vf', 'scale=64:64,format=gray', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    return sum(out) / len(out), max(out)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.books = Books(self.tmp.name)
        self.book = self.books.import_book(title='The Lamp', text='\n'.join(LINES))['book_id']

    def call(self, **args):
        return json.loads(package.invoke('pagecast_audiogram', {'book_id': self.book, **args}, {}, self.tmp.name))


class SelectionTests(Fixture):
    """Span choice, caption timing and limits need no video encode (dry_run) where possible."""
    def setUp(self):
        super().setUp(); produce(self.books, self.book, SECONDS, timed={0, 1})

    def test_selectors_snap_outward_to_whole_passages(self):
        by_words = self.call(chapter=0, first_words='second SENTENCE', last_words='fourth sentence arrives', dry_run=True)
        self.assertEqual(by_words['passage_ids'], [1, 2, 3])
        self.assertEqual((by_words['chapter_start_seconds'], by_words['chapter_end_seconds'], by_words['seconds']), (6, 26, 20))
        # 6.5 s is inside passage 1 (6 to 13): the start moves back to 6; 25.9 s is inside passage 3 (18 to 26): the end moves forward to 26.
        by_time = self.call(chapter=0, start_seconds=6.5, end_seconds=25.9, dry_run=True)
        self.assertEqual((by_time['passage_ids'], by_time['chapter_start_seconds'], by_time['chapter_end_seconds']), ([1, 2, 3], 6, 26))
        exact = self.call(chapter=0, start_seconds=6, end_seconds=13, dry_run=True)   # exactly one passage, not two
        self.assertEqual(exact['passage_ids'], [1])
        by_ids = self.call(chapter=0, first_passage_id=4, last_passage_id=5, dry_run=True)
        self.assertEqual((by_ids['passage_ids'], by_ids['text']), ([4, 5], [LINES[4], LINES[5]]))
        self.assertTrue(by_ids['dry_run']); self.assertFalse((Path(self.tmp.name) / self.book / 'audiograms').exists())

    def test_bad_ranges_and_choices_are_plain_errors(self):
        for args, text in [({'first_passage_id': 5, 'last_passage_id': 2}, 'before the start'), ({'first_passage_id': 99, 'last_passage_id': 100}, 'not in this chapter'),
                           ({'start_seconds': 0, 'end_seconds': 500}, 'after the end'), ({'start_seconds': 400, 'end_seconds': 410}, 'after the end'),
                           ({'start_seconds': -1, 'end_seconds': 20}, 'seconds'), ({'first_words': 'no such words', 'last_passage_id': 3}, 'not found'),
                           ({'first_passage_id': 3, 'last_words': 'second sentence'}, 'at or after'), ({'first_passage_id': 1}, 'exactly one'),
                           ({'first_passage_id': 1, 'start_seconds': 0, 'last_passage_id': 2}, 'exactly one'), ({'first_passage_id': 1, 'last_passage_id': 2, 'shape': 'tall'}, 'shape')]:
            with self.subTest(args=args):
                result = self.call(chapter=0, dry_run=True, **args); self.assertIn(text, result['error'])
        self.assertIn('Unknown chapter', self.call(chapter=3, first_passage_id=0, last_passage_id=1)['error'])

    def test_too_short_and_too_long(self):
        self.assertNotIn('error', self.call(chapter=0, first_passage_id=2, last_passage_id=2, dry_run=True))
        with patch.object(clip, 'MIN_SECONDS', 5.5): self.assertIn('at least 5.5', self.call(chapter=0, first_passage_id=2, last_passage_id=2, dry_run=True)['error'])
        second = Books(self.tmp.name); long_book = second.import_book(title='Long', text='\n'.join(f'Passage number {n} is here.' for n in range(10)))['book_id']
        produce(second, long_book, [25] * 10, silent=True)
        result = json.loads(package.invoke('pagecast_audiogram', {'book_id': long_book, 'chapter': 0, 'first_passage_id': 0, 'last_passage_id': 7, 'dry_run': True}, {}, self.tmp.name))
        self.assertIn('limited to 180', result['error'])
        ok = json.loads(package.invoke('pagecast_audiogram', {'book_id': long_book, 'chapter': 0, 'first_passage_id': 0, 'last_passage_id': 6, 'dry_run': True}, {}, self.tmp.name))
        self.assertEqual(ok['seconds'], 175); self.assertIn('length_note', ok)

    def test_chapter_not_produced_yet(self):
        other = self.books.import_book(title='Unrendered', text='One line here.\nAnother line there.')['book_id']
        result = json.loads(package.invoke('pagecast_audiogram', {'book_id': other, 'chapter': 0, 'first_passage_id': 0, 'last_passage_id': 1}, {}, self.tmp.name))
        self.assertIn('not fully produced', result['error']); self.assertFalse((Path(self.tmp.name) / other / 'audiograms').exists())
        # half a chapter is not enough either
        _, passages, _ = self.books.plan(other); target = Path(passages[0]['audio_path']); target.parent.mkdir(parents=True); tone(target, 6)
        self.assertIn('1 of 2', json.loads(package.invoke('pagecast_audiogram', {'book_id': other, 'chapter': 0, 'first_passage_id': 0, 'last_passage_id': 1}, {}, self.tmp.name))['error'])

    def test_caption_times_are_relative_to_the_clip_and_follow_word_timing(self):
        long_line = 'Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega again.'
        self.books.edit(self.book, 1, long_line)
        produce(self.books, self.book, SECONDS, timed={1})
        cues = []
        _, passages, _ = self.books.plan(self.book)
        metadata = json.loads((Path(passages[1]['audio_path']).parent / 'receipt.json').read_text())['provider_metadata']
        cues = clip.passage_cues(long_line, 7.0, 3.0, metadata, 70)   # as if the passage starts 3 s into the clip
        self.assertGreater(len(cues), 1); self.assertEqual({c['kind'] for c in cues}, {'word'})
        self.assertEqual(cues[0]['start'], 3.0); self.assertAlmostEqual(cues[-1]['end'], 10.0)
        self.assertTrue(all(a['end'] == b['start'] for a, b in zip(cues, cues[1:])))
        words = long_line.split(); step = 7.0 / len(words)
        second_first_word = len(cues[0]['text'].split())
        self.assertAlmostEqual(cues[1]['start'], 3.0 + second_first_word * step, places=6)   # the first word of piece two starts then
        self.assertTrue(all(len(c['text']) <= 70 for c in cues))
        estimated = clip.passage_cues(long_line, 7.0, 0.0, {}, 70)
        self.assertEqual({c['kind'] for c in estimated}, {'estimated'}); self.assertAlmostEqual(estimated[-1]['end'], 7.0)
        for text in ('\u65e5\u672c\u8a9e' * 40, 'x' * 200): self.assertTrue(all(len(c['text']) <= 70 for c in clip.passage_cues(text, 9.0, 0.0, {}, 70)))

    def test_srt_and_ass_escaping(self):
        self.assertEqual(clip.timestamp(3661.5, True), '01:01:01,500'); self.assertEqual(clip.timestamp(1.234, False), '0:00:01.23')
        escaped = clip.ass_escape('a\\N b\\h {x} \\')
        self.assertNotIn('\\N', escaped.replace('\\\u2060N', '')); self.assertIn('\\{x\\}', escaped)
        self.assertEqual(clip.srt_text([{'start': 0, 'end': 1.5, 'text': 'Hi', 'speaker': 'Mira'}]), '1\n00:00:00,000 --> 00:00:01,500\nMira: Hi\n\n')


@unittest.skipUnless(HAVE_FFMPEG, 'FFmpeg is not installed')
class RenderTests(Fixture):
    def setUp(self):
        super().setUp(); produce(self.books, self.book, SECONDS, timed={1, 2})

    def make_cover(self, name='cover.png'):
        path = Path(self.tmp.name) / name
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=600x900:d=1', '-frames:v', '1', str(path)], check=True)
        return str(path)

    def test_every_shape_has_the_right_size_codecs_and_length(self):
        for shape, size in (('vertical', (1080, 1920)), ('square', (1080, 1080)), ('wide', (1920, 1080))):
            with self.subTest(shape=shape):
                result = self.call(chapter=0, first_passage_id=1, last_passage_id=2, shape=shape)
                self.assertNotIn('error', result, result)
                video, audio, seconds = probe(result['path'])
                self.assertEqual((video['width'], video['height'], video['codec_name'], video['pix_fmt'], audio['codec_name']), (*size, 'h264', 'yuv420p', 'aac'))
                self.assertTrue(video['width'] % 2 == video['height'] % 2 == 0)
                self.assertAlmostEqual(seconds, 12.0, delta=.15); self.assertAlmostEqual(result['seconds'], 12.0, delta=.15)
                self.assertEqual((result['width_height'], result['cover']), (list(size), 'none (plain dark background)'))
                self.assertTrue(Path(result['path']).name.endswith('.mp4') and Path(result['srt_path']).read_text().startswith('1\n00:00:00,000 -->'))
                self.assertEqual(result['text'], [LINES[1], LINES[2]]); self.assertEqual(result['caption_timing'], 'word')
                self.assertIn('nothing was uploaded', result['rights_notice']); self.assertFalse(result['uploaded'])
                self.assertEqual(result['passage_ids'], [1, 2]); self.assertEqual(result['chapter_title'], 'Chapter1')

    def test_audio_is_the_cut_span_with_fades(self):
        result = self.call(chapter=0, first_passage_id=1, last_passage_id=1)
        loudness = subprocess.run(['ffmpeg', '-nostdin', '-v', 'info', '-i', result['path'], '-af', 'astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-', '-f', 'null', '-'], capture_output=True, text=True).stdout
        levels = [float(line.split('=')[1]) for line in loudness.splitlines() if 'RMS_level' in line and '-inf' not in line]
        self.assertGreater(len(levels), 10); self.assertLess(levels[0], levels[len(levels) // 2] - 6)   # faded in
        self.assertLess(levels[-1], levels[len(levels) // 2] - 6)                                        # and out

    def test_cover_and_waveform_change_the_picture(self):
        plain = self.call(chapter=0, first_passage_id=1, last_passage_id=1, shape='square')
        covered = self.call(chapter=0, first_passage_id=1, last_passage_id=1, shape='square', cover_path=self.make_cover(), waveform=True)
        self.assertNotIn('error', covered, covered); self.assertEqual(covered['cover'], 'used'); self.assertTrue(covered['waveform'])
        self.assertNotEqual(plain['path'], covered['path'])
        self.assertLess(frame_stats(plain['path'], 3)[0], frame_stats(covered['path'], 3)[0])   # a cover brightens a plain dark frame
        for bad in ('/nonexistent/cover.png', str(Path(self.tmp.name) / 'notes.txt')):
            Path(self.tmp.name, 'notes.txt').write_text('not an image')
            self.assertIn('error', self.call(chapter=0, first_passage_id=1, last_passage_id=1, shape='square', cover_path=bad))
        fake = Path(self.tmp.name) / 'fake.png'; fake.write_text('not an image')
        self.assertIn('not a readable image', self.call(chapter=0, first_passage_id=1, last_passage_id=1, shape='square', cover_path=str(fake))['error'])

    def test_hostile_text_does_not_break_the_render(self):
        hostile = ['He said "no": 100% sure \\N not \\h here; \'quote\' {\\i1}tag{\\i0} [x]=y,z', '\u65e5\u672c\u8a9e\u306e\u30c6\u30ad\u30b9\u30c8\u3092\u8aad\u3080\u3002\u4eca\u65e5\u306f\u3044\u3044\u5929\u6c17\u3067\u3059\u306d\u3002 emoji \U0001f600\U0001f680 caf\u00e9 \u00fcber \u0645\u0631\u062d\u0628\u0627', "C:\\path\\to\\file %s %d $HOME `ls` $(id) ; & | > ' \" \\"]
        for index, text in enumerate(hostile): self.books.edit(self.book, index, text)
        produce(self.books, self.book, SECONDS)
        result = self.call(chapter=0, first_passage_id=0, last_passage_id=2, shape='square')
        self.assertNotIn('error', result, result)
        self.assertEqual(result['text'][:3], hostile)
        srt = Path(result['srt_path']).read_text(encoding='utf-8')
        for text in hostile: self.assertIn(text.split()[0], srt)
        self.assertIn('\U0001f600', srt); self.assertIn('\u65e5\u672c\u8a9e', srt)
        self.assertAlmostEqual(probe(result['path'])[2], 18.0, delta=.2)
        self.assertGreater(frame_stats(result['path'], 3)[1], 60)   # white caption pixels are on screen
        odd = Books(self.tmp.name); odd_book = odd.import_book(title='Odd "Title": 100% {\\N} \\ \u65e5\u672c %(x)s', text='One line here.\nAnother line there.')['book_id']
        produce(odd, odd_book, [6, 6])
        out = json.loads(package.invoke('pagecast_audiogram', {'book_id': odd_book, 'chapter': 0, 'first_passage_id': 0, 'last_passage_id': 1, 'shape': 'square'}, {}, self.tmp.name))
        self.assertNotIn('error', out, out)

    def test_spoiler_rule_for_speaker_names(self):
        role = self.books.assign(self.book, [2, 3, 4], 'Mira')['speaker']
        self.books.cast_note(self.book, role, 'Mira the Keeper', 'private', reveal_after=3)
        produce(self.books, self.book, SECONDS)
        result = self.call(chapter=0, first_passage_id=1, last_passage_id=5, shape='square')
        self.assertNotIn('error', result, result); self.assertTrue(result['speakers_shown'])
        srt = Path(result['srt_path']).read_text(encoding='utf-8')
        cues = [block.splitlines() for block in srt.strip().split('\n\n')]
        speakers = [block[2].split(': ')[0] for block in cues]
        self.assertEqual(speakers[0], 'Narrator')                           # passage 1
        self.assertNotIn('Mira', ' '.join(speakers[:3]))                    # passages 2 and 3 are at or before the reveal passage
        self.assertTrue(any(name == 'Mira the Keeper' for name in speakers))  # passage 4 is after it
        self.assertNotIn('Voice ', srt)                                     # the neutral placeholder is left out, not shown
        self.assertNotIn('private', json.dumps(result))
        # a single-voice chapter shows no speaker names at all
        one = Books(self.tmp.name); book = one.import_book(title='Solo', text='One line here.\nAnother line there.')['book_id']; produce(one, book, [6, 6])
        solo = json.loads(package.invoke('pagecast_audiogram', {'book_id': book, 'chapter': 0, 'first_passage_id': 0, 'last_passage_id': 1, 'shape': 'square'}, {}, self.tmp.name))
        self.assertFalse(solo['speakers_shown']); self.assertNotIn('Narrator:', Path(solo['srt_path']).read_text())

    def test_no_word_timing_is_said_plainly_and_captions_still_made(self):
        result = self.call(chapter=0, first_passage_id=4, last_passage_id=5, shape='square')
        self.assertEqual(result['caption_timing'], 'estimated'); self.assertIn('no word timing', result['caption_timing_note'])
        self.assertGreaterEqual(result['captions'], 2)

    def test_ffmpeg_missing_and_missing_filters(self):
        with patch('shutil.which', return_value=None):
            result = self.call(chapter=0, first_passage_id=1, last_passage_id=2)
        self.assertIn('FFmpeg', result['error']); self.assertIn('not found on PATH', result['error']); self.assertFalse((Path(self.tmp.name) / self.book / 'audiograms').exists())
        class Listing:
            returncode = 0; stdout = ' T. overlay V->V x\n'
        with patch('subprocess.run', return_value=Listing()):
            self.assertIn('lacks', self.call(chapter=0, first_passage_id=1, last_passage_id=2)['error'])

    def test_timeline_chapter_view_gives_the_times_audiogram_takes(self):
        with self.books.db() as db: db.execute("UPDATE passages SET chapter=1, chapter_title='Second' WHERE book=? AND id>=4", (self.book,))
        produce(self.books, self.book, SECONDS)
        rows = self.books.timeline(self.book, chapter=1, include_text=True, limit=2)
        self.assertEqual((rows['total'], rows['times_relative_to'], rows['next_offset']), (4, 'chapter', 2))
        self.assertEqual([(r['passage_id'], r['start_seconds'], r['chapter_start_seconds']) for r in rows['passages']], [(4, 0.0, 0.0), (5, 6.0, 6.0)])
        whole = self.books.timeline(self.book, offset=4, limit=2)
        self.assertEqual((whole['passages'][0]['start_seconds'], whole['passages'][0]['chapter_start_seconds']), (26.0, 0.0))
        result = self.call(chapter=1, first_passage_id=4, last_passage_id=5, shape='square')
        self.assertNotIn('error', result, result); self.assertEqual((result['chapter'], result['chapter_title'], result['chapter_start_seconds']), (1, 'Second', 0.0))
        with self.assertRaises(ValueError): self.books.timeline(self.book, chapter=7)

    def test_tool_is_declared_everywhere(self):
        self.assertIn('pagecast_audiogram', package.TOOLS)
        self.assertIn('pagecast_audiogram', (ROOT / 'plugin.yaml').read_text())
        self.assertIn('pagecast_audiogram', json.dumps(json.loads((ROOT / 'llmwiki/contracts.json').read_text())))
        self.assertIn('pagecast_audiogram', (ROOT / 'llmwiki/tools.md').read_text())
        self.assertIn('pagecast_audiogram', (ROOT / 'skills/pagecast-director/SKILL.md').read_text())
        self.assertIn('pagecast_audiogram', (ROOT / 'README.md').read_text())


if __name__ == '__main__': unittest.main()

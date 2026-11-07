import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import wave
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pagecast_test', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(spec); sys.modules[spec.name] = package; spec.loader.exec_module(package)
from pagecast_test.books import Books, inspect_wav, verify_cache
from pagecast_test.importers import import_file, reference, segment

TEXT = 'The observatory lights flickered.\n“Did you save the coordinates?”\n“Twice. Let’s begin.”'


class ImportTests(unittest.TestCase):
    def test_database_is_private_before_sqlite_opens_it(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            original = package.books.sqlite3.connect
            modes = []
            def connect(path, *args, **kwargs):
                modes.append(Path(path).stat().st_mode & 0o777)
                return original(path, *args, **kwargs)
            previous = os.umask(0)
            try:
                with patch.object(package.books.sqlite3, 'connect', side_effect=connect):
                    books = Books(tmp)
                    books.import_book(text='Original private fixture.')
                self.assertTrue(modes)
                self.assertTrue(all(mode == 0o600 for mode in modes))
            finally:
                os.umask(previous)

    def test_symlink_database_is_rejected(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            root = Path(tmp); outside = root/'outside.db'; outside.write_text('fixture')
            (root/'books.db').symlink_to(outside)
            with self.assertRaises((OSError, ValueError)): Books(root)
            self.assertEqual(outside.read_text(), 'fixture')

    def test_book_lock_rejects_a_second_owner(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            books = Books(tmp); ident = books.import_book(text='Fictional fixture.')['book_id']
            with books.lock(ident):
                with self.assertRaisesRegex(RuntimeError, 'busy'):
                    with books.lock(ident): pass

    def test_quote_offsets_apostrophes_and_scene_breaks(self):
        paragraphs = ["Don't lose the map.", '“We won’t,” said Mina.', '***']
        units = segment([{'title': 'One', 'paragraphs': paragraphs}])
        self.assertIsNone(units[0]['quote_id'])
        self.assertEqual(sum(u['quote_id'] is not None for u in units), 1)
        for unit in units:
            self.assertEqual(paragraphs[unit['paragraph']][unit['start']:unit['end']], unit['text'])
        self.assertFalse(any(u['text'] == '***' for u in units))

    def test_private_credential_directory_is_not_a_book_source(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            private = Path(tmp)/'.codex'
            private.mkdir()
            source = private/'fixture.txt'
            source.write_text('not a real credential')
            with self.assertRaisesRegex(ValueError, 'Credential/configuration'):
                import_file(str(source))

    def test_mixed_case_private_directory_is_not_a_book_or_voice_source(self):
        from pagecast_test.reference_paths import resolve_reference
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            for name in ('.CoDeX', '.HeRmEs'):
                folder=Path(tmp)/name;folder.mkdir();source=folder/'fixture.txt';source.write_text('fictional')
                with self.assertRaises(ValueError):import_file(str(source))
                with self.assertRaises(ValueError):resolve_reference(str(source),Path(tmp)/'plugin')

    def test_profile_book_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            profile = Path(tmp)/'custom-profile'
            library = profile/'plugin-data'/'epub-clinic'
            library.mkdir(parents=True)
            source = library/'book.txt'
            source.write_text('An original chapter.')
            books = Books(profile/'plugin-data'/'pagecast-director')
            with self.assertRaisesRegex(ValueError, 'explicit opt-in'):
                books.import_book(source_path=str(source))
            result = books.import_book(source_path=str(source), allow_profile_books=True)
            self.assertEqual(result['passages'], 1)
            unrelated = profile/'secret.txt'
            unrelated.write_text('not a real credential')
            with self.assertRaisesRegex(ValueError, 'Credential/configuration'):
                books.import_book(source_path=str(unrelated), allow_profile_books=True)

    def test_epub_spine_unescaped_spaces_and_no_archive_traversal(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            epub = Path(tmp) / 'original.epub'
            with zipfile.ZipFile(epub, 'w') as z:
                z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
                z.writestr('OPS/book.opf', '<package><metadata><title>Original</title></metadata><manifest><item id="a" href="first chapter.xhtml"/><item id="b" href="second%20chapter.xhtml"/></manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>')
                z.writestr('OPS/first chapter.xhtml', '<html><head><style>do not read</style></head><body><p>First.</p></body></html>')
                z.writestr('OPS/second chapter.xhtml', '<html><body><p>Second &amp; safe.</p></body></html>')
            title, chapters, _ = import_file(str(epub))
            self.assertEqual(title, 'Original')
            self.assertEqual(chapters[0]['paragraphs'], ['Second & safe.'])
            self.assertEqual(chapters[1]['paragraphs'], ['First.'])
        with self.assertRaises(ValueError): reference('OPS/book.opf', '../../secret.txt')


@unittest.skipUnless(shutil.which('flite') and shutil.which('ffmpeg'), 'Flite/FFmpeg required')
class RenderTests(unittest.TestCase):
    def test_malformed_wav_with_matching_hash_is_rejected(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            books = Books(tmp); book_id = books.import_book(text='Synthetic passage.')['book_id']
            self.assertEqual(books.render(book_id)['state'], 'complete')
            path = Path(books.plan(book_id)[1][0]['audio_path'])
            path.write_bytes(b'not a WAV')
            receipt_path = path.parent/'receipt.json'; receipt = json.loads(receipt_path.read_text())
            receipt['audio_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'incomplete or changed'): verify_cache(path)

    def test_cache_replacement_during_verification_is_rejected(self):
        from pagecast_test import books as module
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            books = Books(tmp); book_id = books.import_book(text='Synthetic passage.')['book_id']
            self.assertEqual(books.render(book_id)['state'], 'complete')
            path = Path(books.plan(book_id)[1][0]['audio_path'])
            replacement = path.with_name('replacement.wav'); replacement.write_bytes(path.read_bytes())
            original = module.hashlib.file_digest
            def replace(stream, algorithm):
                result = original(stream, algorithm)
                os.replace(replacement, path)
                return result
            with patch.object(module.hashlib, 'file_digest', side_effect=replace):
                with self.assertRaisesRegex(ValueError, 'incomplete or changed'): verify_cache(path)

    def test_large_timeline_paging_reuses_verified_cache(self):
        from pagecast_test import books as module
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            books = Books(tmp); book_id = books.import_book(text='Synthetic test.')['book_id']
            book = {'revision': 1, 'source_hash': 'synthetic'}
            passages = [{'id': i, 'chapter': 0, 'paragraph': i, 'speaker': 'Narrator', 'text': 'Synthetic', 'audio_path': 'fixture-' + str(i % 2)} for i in range(205)]
            with patch.object(books, 'plan', return_value=(book, passages, {})), patch.object(module, 'verify_cache', return_value=1.25) as verify:
                page = books.timeline(book_id, offset=100, limit=100)
            self.assertEqual(page['verified_prefix_passages'], 200)
            self.assertEqual(page['next_offset'], 200)
            self.assertEqual(page['passages'][0]['start_seconds'], 125.0)
            self.assertEqual(page['passages'][-1]['end_seconds'], 250.0)
            self.assertEqual(verify.call_count, 2)
            with patch.object(books, 'plan', return_value=(book, passages, {})), patch.object(module, 'verify_cache', return_value=1.25) as verify:
                full_page = books.timeline(book_id, limit=1000)
                self.assertEqual(len(full_page['passages']), 205); self.assertIsNone(full_page['next_offset'])
                self.assertEqual(verify.call_count, 2)
                with self.assertRaises(ValueError): books.timeline(book_id, limit=101, include_text=True)

    def test_three_voices_partial_resume_and_selective_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); book_id = books.import_book('Original scene', text=TEXT)['book_id']
            units = books.get(book_id)['passages']; self.assertEqual(len(units), 3)
            books.assign(book_id, [1], 'Mina'); books.assign(book_id, [2], 'Jules')
            books.set_voice(book_id, 'Mina', voice='slt'); books.set_voice(book_id, 'Jules', voice='awb')
            first = books.render(book_id, max_segments=1)
            self.assertEqual(first['state'], 'partial'); self.assertEqual(first['generated'], 1)
            with self.assertRaises(ValueError): books.export(book_id)
            with self.assertRaises(ValueError): books.timeline(book_id, offset=0, limit=2)
            complete = books.render(book_id)
            self.assertEqual(complete['state'], 'complete'); self.assertEqual(complete['generated'], 2); self.assertEqual(complete['reused'], 1)
            first_page = books.timeline(book_id, offset=0, limit=1)
            second_page = books.timeline(book_id, offset=1, limit=2)
            self.assertEqual(first_page['next_offset'], 1)
            self.assertNotIn('text', first_page['passages'][0])
            self.assertEqual(books.timeline(book_id, limit=1, include_text=True)['passages'][0]['text'], units[0]['text'])
            with self.assertRaises(ValueError): books.timeline(book_id, include_text='yes')
            self.assertAlmostEqual(first_page['passages'][0]['end_seconds'], second_page['passages'][0]['start_seconds'])
            self.assertEqual(second_page['verified_prefix_passages'], 3)
            self.assertIsNone(second_page['next_offset'])
            _, before, _ = books.plan(book_id)
            before_audio = {p['id']: Path(p['audio_path']).read_bytes() for p in before}
            with self.assertRaises(ValueError): books.set_voice(book_id, 'Mina', voice='kal16')
            books.set_voice(book_id, 'Mina', voice='kal16', replace_locked=True)
            self.assertEqual(books.get(book_id)['render']['state'], 'needs_render')
            changed = books.render(book_id)
            self.assertEqual(changed['generated'], 1); self.assertEqual(changed['reused'], 2)
            _, after, _ = books.plan(book_id)
            self.assertEqual(before_audio[0], Path(after[0]['audio_path']).read_bytes())
            self.assertEqual(before_audio[2], Path(after[2]['audio_path']).read_bytes())
            self.assertNotEqual(before_audio[1], Path(after[1]['audio_path']).read_bytes())
            exported = books.export(book_id, format='wav')
            self.assertAlmostEqual(books.timeline(book_id, offset=0, limit=100)['passages'][-1]['end_seconds'], exported['seconds'], places=5)
            self.assertGreater(inspect_wav(exported['path']), 1)

    def test_cache_tampering_is_detected_and_retry_preserves_previous_take(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); identifier = books.import_book(text='An original short line.')['book_id']
            books.render(identifier)
            path = Path(books.plan(identifier)[1][0]['audio_path'])
            data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
            with self.assertRaises(ValueError): books.export(identifier)
            result = books.retry(identifier, [0])
            self.assertEqual(len(result['previous_takes_preserved']), 1)
            self.assertEqual(books.render(identifier)['generated'], 1)
            verify_cache(books.plan(identifier)[1][0]['audio_path'])

    def test_m4b_metadata_and_cast_change_during_render(self):
        import subprocess
        from pagecast_test import books as module
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); identifier = books.import_book('Original #1; safe', text=TEXT)['book_id']
            original_run = module.run
            changed = False
            def run_and_change(args, **kwargs):
                nonlocal changed
                result = original_run(args, **kwargs)
                if args[0] == 'flite' and not changed:
                    changed = True; books.set_voice(identifier, 'Narrator', voice='slt')
                return result
            with patch.object(module, 'run', side_effect=run_and_change):
                self.assertEqual(books.render(identifier)['state'], 'stale')
            self.assertEqual(books.render(identifier)['state'], 'complete')
            output = books.export(identifier)
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_chapters', '-of', 'json', output['path']]))
            self.assertEqual(info['format']['tags']['title'], 'Original #1; safe')
            self.assertEqual(len(info['chapters']), 1)

    def test_assignment_is_atomic_and_text_edit_affects_one_passage(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Books(tmp); identifier = books.import_book(text=TEXT)['book_id']
            with self.assertRaises(ValueError): books.assign(identifier, [0, 999], 'Someone')
            self.assertEqual(books.get(identifier)['passages'][0]['speaker'], 'Narrator')
            books.render(identifier)
            books.edit(identifier, 1, '“The coordinates are saved.”')
            result = books.render(identifier)
            self.assertEqual(result['generated'], 1); self.assertEqual(result['reused'], 2)


if __name__ == '__main__': unittest.main()

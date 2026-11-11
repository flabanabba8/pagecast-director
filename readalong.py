"""Portable private read-along: no server, network, external scripts or credentials."""
import hashlib
import json
import math
import re
from pathlib import Path
import zipfile


def word_spans(text, metadata, duration):
    if not isinstance(metadata, dict) or not isinstance(metadata.get('timestamp_info', {}), dict): return []
    alignment = metadata.get('timestamp_info', {}).get('wordAlignment', {})
    if not isinstance(alignment, dict): return []
    words = alignment.get('words', [])
    starts, ends = alignment.get('wordStartTimeSeconds', []), alignment.get('wordEndTimeSeconds', [])
    if not all(isinstance(v, list) for v in (words, starts, ends)) or not (len(words) == len(starts) == len(ends)): return []
    spans, cursor, previous = [], 0, 0
    for word, start, end in zip(words, starts, ends):
        if not isinstance(word, str) or type(start) not in (float, int) or type(end) not in (float, int): return []
        if not (math.isfinite(start) and math.isfinite(end) and previous <= start <= end <= duration + .05): return []
        previous = start
        # Actual TTS-2 alignment includes silent direction tags, whitespace and
        # a trailing empty token. They are not missing reader words.
        if not word.strip() or re.fullmatch(r'\[[^\]\n]*\]|<[^>]*>', word): continue
        position = text.find(word, cursor)
        if position < 0 or any(c.isalnum() for c in text[cursor:position]): return []
        spans.append({'from': len(text[:position].encode('utf-16-le')) // 2, 'to': len(text[:position + len(word)].encode('utf-16-le')) // 2, 'start': start, 'end': end})
        cursor, previous = position + len(word), start
    # Normalized words/IPA may not match source. Keep honest passage highlighting.
    return spans if not any(c.isalnum() for c in text[cursor:]) else []


def package(book, passages, audio):
    rows, elapsed = [], 0.0
    for passage in passages:
        receipt = json.loads((Path(passage['audio_path']).parent / 'receipt.json').read_text())
        duration = receipt['seconds']
        rows.append({'text': passage['text'], 'speaker': passage['speaker'], 'chapter': passage['chapter_title'], 'chapter_index': passage['chapter'],
                     'start': elapsed, 'end': elapsed + duration,
                     'words': word_spans(passage['text'], receipt.get('provider_metadata', {}), duration)})
        elapsed += duration
    source = Path(audio['path'])
    with source.open('rb') as stream: checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = {'version': 1, 'title': book['title'], 'book_id': book['id'], 'revision': book['revision'],
                'series': book.get('series'), 'audio': 'audiobook.m4b', 'audio_sha256': checksum, 'passages': rows, 'credit': audio.get('credit', '')}
    payload = json.dumps(manifest, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    html = Path(__file__).with_name('reader.html').read_text().replace('/*BOOK_DATA*/null', payload)
    output = source.with_suffix('.readalong.zip'); temporary = output.with_suffix('.part.zip')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            archive.write(source, 'audiobook.m4b')
            archive.writestr('reader.html', html)
            archive.writestr('book.json', json.dumps(manifest, ensure_ascii=False))
            archive.writestr('READ-ME.txt', 'Extract this ZIP on your Android phone or PC. Open reader.html in Chrome or Firefox, choose the extracted audiobook.m4b and press Play. No connection, account or speech generation is needed. If your file manager opens a static HTML preview, use Open with a browser. You can also copy reader.html to a browser-accessible location. Highlighting uses provider word timing where it matches the source, otherwise passage timing. Browser background playback and local-file opening vary by device. The M4B also plays in audiobook apps.\n')
        temporary.replace(output)
    finally: temporary.unlink(missing_ok=True)
    return {**audio, 'path': str(output), 'format': 'readalong', 'word_timed_passages': sum(bool(r['words']) for r in rows)}

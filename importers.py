"""Bounded text-first TXT/EPUB import; preserve source text and spine order."""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import posixpath
import re
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

MAX_TEXT = 1_000_000


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'): self.skip += 1
        if not self.skip and tag in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'li', 'section'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head') and self.skip: self.skip -= 1
        if not self.skip and tag in ('p', 'div', 'h1', 'h2', 'h3', 'li', 'section'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)
    def paragraphs(self):
        return [re.sub(r'\s+', ' ', p).strip() for p in ''.join(self.parts).splitlines() if p.strip()]


def reference(base, href):
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        raise ValueError('External EPUB chapter references are unsupported')
    name = unquote(parsed.path)
    normalized = posixpath.normpath(posixpath.join(posixpath.dirname(base), name))
    if normalized.startswith('/') or normalized == '..' or normalized.startswith('../') or '\\' in normalized:
        raise ValueError('EPUB reference leaves its archive')
    return normalized


def import_file(path, profile_data=None, allow_profile_books=False):
    if type(allow_profile_books) is not bool: raise ValueError('allow_profile_books must be boolean')
    source = Path(path).expanduser()
    if not source.is_absolute() or source.is_symlink() or source.suffix.lower() not in ('.txt', '.epub'):
        raise ValueError('Choose an absolute regular TXT or EPUB path, not a symlink')
    original_parts = source.parts
    source = source.resolve(strict=True)
    private = ('.ssh', '.gnupg', '.aws', '.azure', '.codex', '.docker', '.kube', '.pki', '.config')
    data_root = Path(profile_data).resolve() if profile_data is not None else None
    profile_home = data_root.parent if data_root is not None and data_root.name.casefold() == 'plugin-data' else None
    allowed = allow_profile_books and profile_home is not None and source.is_relative_to(data_root)
    protected = any(part.casefold() == '.hermes' for part in (*original_parts, *source.parts)) or (profile_home is not None and source.is_relative_to(profile_home))
    if any(part.casefold() in private for part in (*original_parts, *source.parts)) or protected and not allowed:
        raise ValueError('Credential/configuration folders are not book sources; selected profile plugin books require explicit opt-in')
    if not source.is_file() or source.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Book must be a regular file of at most16 MiB')
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    if source.suffix.lower() == '.txt':
        text = source.read_text(encoding='utf-8-sig')
        if len(text) > MAX_TEXT: raise ValueError('Book exceeds one million characters')
        return source.stem, [{'title': 'Chapter1', 'paragraphs': [p.strip() for p in text.splitlines() if p.strip()]}], fingerprint
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > 32 * 1024 * 1024:
            raise ValueError('EPUB exceeds2000 files or32 MiB expanded')
        names = {e.filename for e in entries}
        if len(names) != len(entries): raise ValueError('EPUB has duplicate archive entries')
        for entry in entries:
            if entry.flag_bits & 1 or (entry.file_size and entry.file_size / max(1, entry.compress_size) > 300):
                raise ValueError('Encrypted or excessively compressed EPUB is unsupported')
            if entry.filename.startswith('/') or '..' in entry.filename.split('/') or '\\' in entry.filename:
                raise ValueError('Unsafe EPUB entry path')
        def xml(name):
            data = archive.read(name)
            if b'<!ENTITY' in data.upper(): raise ValueError('EPUB XML entities are unsupported')
            return ET.fromstring(data)
        container = xml('META-INF/container.xml')
        roots = [e for e in container.iter() if e.tag.rsplit('}', 1)[-1] == 'rootfile']
        if not roots: raise ValueError('EPUB container has no rootfile')
        opf_name = reference('', roots[0].attrib['full-path'])
        opf = xml(opf_name)
        local = lambda tag: [e for e in opf.iter() if e.tag.rsplit('}', 1)[-1] == tag]
        titles = local('title')
        title = ''.join(titles[0].itertext()).strip() if titles else source.stem
        manifest = {e.attrib['id']: e for e in local('item') if 'id' in e.attrib}
        chapters, total = [], 0
        for itemref in local('itemref'):
            if itemref.attrib.get('linear') == 'no': continue
            item = manifest.get(itemref.attrib.get('idref'))
            if item is None: raise ValueError('EPUB spine references a missing manifest item')
            member = reference(opf_name, item.attrib.get('href', ''))
            parser = TextHTML(); parser.feed(archive.read(member).decode('utf-8-sig'))
            paragraphs = parser.paragraphs()
            total += sum(map(len, paragraphs))
            if total > MAX_TEXT: raise ValueError('Book exceeds one million characters')
            if paragraphs: chapters.append({'title': f'Chapter{len(chapters)+1}', 'paragraphs': paragraphs})
        if not chapters: raise ValueError('EPUB contains no readable spine text')
        return title, chapters, fingerprint


# Quote detection follows PageCast's source-preserving style selection. Apostrophes
# inside words are not dialogue delimiters. No speaker identity is inferred here.
STYLES = [('„', '“'), ('“', '”'), ('"', '"'), ('«', '»'), ('‘', '’'), ("'", "'")]


def opening(text, index, quote):
    return text[index] == quote and (quote not in ('‘', "'") or
        ((index == 0 or not text[index - 1].isalnum()) and index + 1 < len(text) and not text[index + 1].isspace()))


def closing(text, index, quote):
    return text[index] == quote and not (quote in ('’', "'") and index > 0 and index + 1 < len(text) and text[index - 1].isalnum() and text[index + 1].isalnum())


def speech(text):
    return any(not c.isspace() and not unicodedata.category(c).startswith('P') for c in text)


def chunks(text, offset):
    cursor = 0
    while cursor < len(text):
        limit = min(len(text), cursor + 300)
        words = list(re.finditer(r'\S+', text[cursor:limit]))
        if len(words) > 60: limit = cursor + words[59].end()
        if limit < len(text):
            stops = list(re.finditer(r'[.!?][”"\']?\s+', text[cursor:limit]))
            if stops: limit = cursor + stops[-1].end()
            elif ' ' in text[cursor:limit]: limit = text.rfind(' ', cursor, limit) + 1
        unit = text[cursor:limit]
        if unit.strip(): yield {'text': unit, 'start': offset + cursor, 'end': offset + limit}
        cursor = limit


def segment(chapters):
    paragraphs = [p for chapter in chapters for p in chapter['paragraphs']]
    def score(style):
        a, b = style
        return sum(1 + 2 * (p.find(b, i + 1) >= 0) for p in paragraphs for i in range(len(p)) if opening(p, i, a))
    a, b = max(STYLES, key=score)
    result = []
    for chapter_index, chapter in enumerate(chapters):
        for paragraph_index, paragraph in enumerate(chapter['paragraphs']):
            if re.fullmatch(r'\s*(?:\*\s*){3,}', paragraph): continue
            cursor, quote = 0, 0
            paragraph_units = []
            while cursor < len(paragraph):
                start = next((i for i in range(cursor, len(paragraph)) if opening(paragraph, i, a)), len(paragraph))
                for unit in chunks(paragraph[cursor:start], cursor):
                    paragraph_units.append({**unit, 'chapter': chapter_index, 'chapter_title': chapter['title'], 'paragraph': paragraph_index, 'quote_id': None})
                if start == len(paragraph): break
                end = next((i + 1 for i in range(start + 1, len(paragraph)) if closing(paragraph, i, b)), len(paragraph))
                for unit in chunks(paragraph[start:end], start):
                    paragraph_units.append({**unit, 'chapter': chapter_index, 'chapter_title': chapter['title'], 'paragraph': paragraph_index, 'quote_id': f'{chapter_index}.{paragraph_index}.{quote}'})
                cursor, quote = end, quote + 1
            attached = []
            for unit in paragraph_units:
                if attached and attached[-1]['end'] == unit['start'] and (not speech(attached[-1]['text']) or not speech(unit['text'])):
                    previous = attached[-1]
                    previous['quote_id'] = previous['quote_id'] if speech(previous['text']) else unit['quote_id']
                    previous.update(text=previous['text'] + unit['text'], end=unit['end'])
                else: attached.append(unit)
            result.extend(unit for unit in attached if speech(unit['text']))
    if not result or len(result) > 20000: raise ValueError('Book must contain1–20000 speakable passages')
    return result

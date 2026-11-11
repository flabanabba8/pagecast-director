"""Bounded, read-only access to the packaged LLM wiki in native and MCP hosts."""
import hashlib
from pathlib import Path

TOPICS = ('index', 'providers', 'runtimes', 'project-lessons', 'tools', 'task-guide', 'contracts')


def read(topic='index', offset=0, limit=6000):
    if topic not in TOPICS:
        raise ValueError('Choose a bundled knowledge topic: ' + ', '.join(TOPICS))
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 200 <= limit <= 12000:
        raise ValueError('Use a nonnegative character offset and limit between 200 and 12000')
    path = Path(__file__).parent / 'llmwiki' / (topic + ('.json' if topic == 'contracts' else '.md'))
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('Symlinked knowledge is unsupported')
    with path.open('rb') as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError('Knowledge topic exceeds its bounded package contract')
    text = data.decode('utf-8')
    end = min(len(text), offset + limit)
    return {'topic': topic, 'topics': list(TOPICS), 'status': 'source-derived reference; not a live backend check',
            'sha256': hashlib.sha256(data).hexdigest(), 'offset': offset, 'text': text[offset:end],
            'next_offset': end if end < len(text) else None}

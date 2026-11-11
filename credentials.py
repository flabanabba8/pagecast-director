"""TTS credentials only. Harness model authentication is never read or forwarded."""
from contextlib import contextmanager
from contextvars import ContextVar
import os

_standalone = ContextVar('pagecast_standalone', default=False)


@contextmanager
def standalone():
    token = _standalone.set(True)
    try: yield
    finally: _standalone.reset(token)


def get_secret(name):
    if name not in ('INWORLD_API_KEY', 'ELEVENLABS_API_KEY', 'GEMINI_API_KEY'):
        raise ValueError('Unknown speech credential')
    if _standalone.get(): return os.environ.get(name)
    from agent.secret_scope import get_secret as scoped_secret
    return scoped_secret(name)

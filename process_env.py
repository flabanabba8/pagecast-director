"""Pass OS/session/network controls to helpers, not cloud API credentials."""
import os

_NAMES = (
    'PATH', 'HOME', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'TEMP', 'TMP',
    'DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
    'DBUS_SESSION_BUS_ADDRESS', 'PULSE_SERVER', 'PULSE_COOKIE', 'PULSE_SINK',
    'SDL_AUDIODRIVER', 'SDL_VIDEODRIVER', 'SDL_RENDER_DRIVER',
    'SSL_CERT_FILE', 'SSL_CERT_DIR', 'SYSTEMROOT', 'WINDIR',
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
)


def process_env():
    return {key: os.environ[key] for key in _NAMES if key in os.environ}

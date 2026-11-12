"""Get the PageCast Android app onto the user's phone.

Downloads only the official release APK from the PageCast GitHub repository, verifies it
against the release's own SHA256SUMS, and (separately, behind an approval) installs it with
adb on one connected phone, or copies a read-along package to the phone. Nothing here reads
app data or uninstalls anything. Device identifiers are never returned.
"""
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
from .process_env import process_env
from pathlib import Path

REPO = 'flabanabba8/PageCast'
LATEST_API = 'https://api.github.com/repos/' + REPO + '/releases/latest'
RELEASES_PAGE = 'https://github.com/' + REPO + '/releases/latest'
ASSET_PREFIX = 'https://github.com/' + REPO + '/releases/download/'
PACKAGE = 'com.geminireader'
MAX_APK = 300 * 1024 * 1024
SIDELOAD = ('On the phone, open ' + RELEASES_PAGE + ' in a browser, download the .apk and tap it to install '
            '(Android will ask you to allow installs from that browser).')
IMPORT_HINT = 'In PageCast on the phone: Import book, then PC audiobook, and choose the .readalong.zip.'


def _get(url, limit, opener=None):
    if not url.startswith('https://'): raise ValueError('Only HTTPS release downloads are allowed')
    request = urllib.request.Request(url, headers={'User-Agent': 'pagecast-director', 'Accept': 'application/vnd.github+json, application/octet-stream'})
    with (opener or urllib.request.urlopen)(request, timeout=120) as response:
        data = response.read(limit + 1)
    if len(data) > limit: raise ValueError('Release file is larger than expected')
    return data


def _adb(runner=None):
    binary = shutil.which('adb')
    def run(*args, timeout=180):
        if runner: return runner(args)
        if not binary: raise ValueError('adb is not installed on this computer. ' + SIDELOAD)
        try: done = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout, env=process_env())
        except subprocess.TimeoutExpired: raise ValueError('The phone did not answer in time; check that it is unlocked and still connected') from None
        return done.returncode, (done.stdout + done.stderr).strip()
    return binary or bool(runner), run


def _one_device(run):
    code, out = run('devices')
    rows = [line.split('\t') for line in out.splitlines()[1:] if '\t' in line]
    ready = [serial for serial, state in rows if state.strip() == 'device']
    waiting = [state.strip() for _, state in rows if state.strip() != 'device']
    if len(ready) != 1:
        raise ValueError(('No phone is connected and authorized for USB or wireless debugging. ' if not ready else 'More than one device is connected; connect only the phone. ')
                         + ('A device is waiting for you to accept the debugging prompt on its screen. ' if waiting else '') + SIDELOAD)
    return ready[0]


def _saved(storage_root):
    folder = Path(storage_root) / 'android-app'; marker = folder / 'current.json'
    if marker.is_file():
        try:
            info = json.loads(marker.read_text()); apk = folder / info['apk']
            if apk.is_file(): return apk, info.get('version', '')
        except (ValueError, KeyError, OSError): pass
    return None, ''


def _numbers(version): return tuple(int(n) for n in re.findall(r'\d+', version or '')[:4])


def _installed_version(run, serial):
    code, out = run('-s', serial, 'shell', 'dumpsys', 'package', PACKAGE)
    found = re.search(r'versionName=([0-9A-Za-z._-]+)', out)
    return found.group(1) if found else None


def release(opener=None):
    info = json.loads(_get(LATEST_API, 2_000_000, opener))
    assets = {a['name']: a['browser_download_url'] for a in info.get('assets', []) if a.get('browser_download_url', '').startswith(ASSET_PREFIX)}
    apks = sorted(name for name in assets if name.endswith('.apk'))
    if len(apks) != 1 or 'SHA256SUMS' not in assets: raise ValueError('The latest PageCast release has no single APK with checksums; open ' + RELEASES_PAGE)
    return {'version': info.get('tag_name', ''), 'apk': apks[0], 'apk_url': assets[apks[0]], 'sums_url': assets['SHA256SUMS']}


def status(storage_root, runner=None, opener=None):
    apk, have = _saved(storage_root)
    available, run = _adb(runner); phone = {'adb_available': bool(available), 'phone_connected': False, 'app_installed': None, 'installed_version': None}
    if available:
        try:
            serial = _one_device(run); phone['phone_connected'] = True
            code, out = run('-s', serial, 'shell', 'pm', 'list', 'packages', PACKAGE)
            phone['app_installed'] = any(line.strip() == 'package:' + PACKAGE for line in out.splitlines())
            if phone['app_installed']: phone['installed_version'] = _installed_version(run, serial)
        except ValueError as exc: phone['note'] = str(exc)
    try: latest = release(opener)['version']
    except (ValueError, OSError, KeyError): latest = None
    newer = bool(latest and phone['installed_version'] and _numbers(latest) > _numbers(phone['installed_version']))
    return {'latest_release': latest, 'latest_release_checked': latest is not None, 'downloaded_apk': apk.name if apk else None, 'downloaded_version': have or None,
            **phone, 'update_available': newer, 'release_page': RELEASES_PAGE,
            'next': ('A newer PageCast release exists: action download fetches it, then pagecast_android_install with update true installs it over the old one (app data is kept; the user is asked first). ' if newer
                     else 'Use action download, then pagecast_android_install (asks the user first). ') + 'Without adb: ' + SIDELOAD, 'import_hint': IMPORT_HINT}


def download(storage_root, opener=None):
    found = release(opener); folder = Path(storage_root) / 'android-app'; folder.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r'[A-Za-z0-9._-]+\.apk', found['apk']): raise ValueError('Unexpected release file name')
    sums = _get(found['sums_url'], 100_000, opener).decode('utf-8', 'replace')
    expected = next((line.split()[0] for line in sums.splitlines() if line.split()[1:2] and line.split()[-1].lstrip('*') == found['apk']), None)
    if not expected or not re.fullmatch(r'[0-9a-f]{64}', expected): raise ValueError('The release checksum file does not list the APK')
    target = folder / found['apk']
    if not (target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected):
        data = _get(found['apk_url'], MAX_APK, opener)
        if hashlib.sha256(data).hexdigest() != expected: raise ValueError('Downloaded APK does not match the release checksum; nothing was saved')
        target.write_bytes(data)
    (folder / 'current.json').write_text(json.dumps({'apk': found['apk'], 'version': found['version'], 'sha256': expected}) + '\n')
    return {'version': found['version'], 'apk': str(target), 'sha256': expected, 'checksum_verified': True, 'source': found['apk_url'],
            'next': 'Call pagecast_android_install to install it on the connected phone (the user is asked first), or: ' + SIDELOAD}


def install(storage_root, readalong_path=None, update=False, runner=None):
    apk, have = _saved(storage_root); saved = [apk] if apk else []
    available, run = _adb(runner)
    if not available: raise ValueError('adb is not installed on this computer. ' + SIDELOAD)
    serial = _one_device(run); result = {}
    code, out = run('-s', serial, 'shell', 'pm', 'list', 'packages', PACKAGE)
    present = any(line.strip() == 'package:' + PACKAGE for line in out.splitlines())
    if present and not update:
        result.update(installed=None, app_installed=True, note='PageCast is already on the phone, so nothing was reinstalled. Pass update true to install the downloaded release over it (app data is kept).')
    else:
        if not saved: raise ValueError('Download the app first with pagecast_android_app action download')
        code, out = run('-s', serial, 'install', '-r', str(saved[-1]))
        if code or 'Success' not in out:
            raise ValueError('The phone refused the install: ' + re.sub(r'\s+', ' ', out)[-300:] + ' Existing app data was not touched.')
        result.update(installed=saved[-1].name, app_installed=True)
    if readalong_path:
        package = Path(readalong_path).expanduser().resolve()
        if not package.is_file() or not package.name.endswith('.readalong.zip'): raise ValueError('Choose an exported .readalong.zip')
        name = re.sub(r'[^A-Za-z0-9._-]', '_', package.name); remote = '/sdcard/Download/' + name
        code, out = run('-s', serial, 'push', str(package), remote)
        if code: raise ValueError('Could not copy the read-along package to the phone: ' + re.sub(r'\s+', ' ', out)[-200:])
        result.update(readalong_on_phone='Download/' + name, import_hint=IMPORT_HINT)
    return result

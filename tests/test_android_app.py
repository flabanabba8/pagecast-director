import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
import test_host_speech as fixture

package = fixture.package
android_app = __import__(package.__name__ + '.android_app', fromlist=['x'])
APK = b'PK-demo-apk-bytes'
SUM = hashlib.sha256(APK).hexdigest()
BASE = 'https://github.com/flabanabba8/PageCast/releases/download/v9.9.9/'


def opener(files):
    def open_(request, timeout=0):
        url = request.full_url
        if url not in files: raise ValueError('unexpected url ' + url)
        return io.BytesIO(files[url])
    return open_


def release(extra=None):
    assets = [{'name': 'PageCast-9.9.9.apk', 'browser_download_url': BASE + 'PageCast-9.9.9.apk'},
              {'name': 'SHA256SUMS', 'browser_download_url': BASE + 'SHA256SUMS'}] + (extra or [])
    return json.dumps({'tag_name': 'v9.9.9', 'assets': assets}).encode()


class AndroidAppTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def files(self, apk=APK, sums=None):
        return {android_app.LATEST_API: release(), BASE + 'PageCast-9.9.9.apk': apk,
                BASE + 'SHA256SUMS': (sums or (SUM + '  PageCast-9.9.9.apk\n')).encode()}

    def test_download_verifies_checksum_and_saves(self):
        out = android_app.download(self.root, opener(self.files()))
        self.assertTrue(out['checksum_verified']); self.assertEqual(Path(out['apk']).read_bytes(), APK)
        self.assertEqual(out['version'], 'v9.9.9')

    def test_bad_checksum_saves_nothing(self):
        with self.assertRaises(ValueError): android_app.download(self.root, opener(self.files(apk=b'tampered')))
        self.assertFalse(list((self.root / 'android-app').glob('*.apk')))

    def test_assets_outside_the_official_repo_are_ignored(self):
        files = self.files(); files[android_app.LATEST_API] = json.dumps({'tag_name': 'v1', 'assets': [
            {'name': 'x.apk', 'browser_download_url': 'https://example.com/x.apk'},
            {'name': 'SHA256SUMS', 'browser_download_url': 'https://example.com/SHA256SUMS'}]}).encode()
        with self.assertRaises(ValueError): android_app.download(self.root, opener(files))

    def test_install_needs_exactly_one_authorized_phone_and_never_returns_serials(self):
        android_app.download(self.root, opener(self.files())); calls = []
        def runner(devices):
            def run(args):
                calls.append(args)
                if args[0] == 'devices': return 0, 'List of devices attached\n' + devices
                if 'pm' in args: return 0, ''
                if 'install' in args: return 0, 'Performing Streamed Install\nSuccess'
                if 'push' in args: return 0, '1 file pushed'
                return 1, 'unexpected'
            return run
        with self.assertRaises(ValueError): android_app.install(self.root, runner=runner(''))
        with self.assertRaises(ValueError): android_app.install(self.root, runner=runner('SECRETSERIAL\tunauthorized\n'))
        with self.assertRaises(ValueError): android_app.install(self.root, runner=runner('A1\tdevice\nB2\tdevice\n'))
        book = self.root / 'story.readalong.zip'; book.write_bytes(b'zip')
        out = android_app.install(self.root, str(book), runner=runner('SECRETSERIAL\tdevice\n'))
        self.assertEqual(out['installed'], 'PageCast-9.9.9.apk'); self.assertEqual(out['readalong_on_phone'], 'Download/story.readalong.zip')
        self.assertNotIn('SECRETSERIAL', json.dumps(out)); self.assertTrue(any('install' in c and '-r' in c for c in calls))
        def present(args):
            if args[0] == 'devices': return 0, 'List of devices attached\nA1\tdevice\n'
            if 'pm' in args: return 0, 'package:com.geminireader\n'
            if 'push' in args: return 0, 'ok'
            self.fail('must not reinstall an existing app without update')
        kept = android_app.install(self.root, str(book), runner=present)
        self.assertIsNone(kept['installed']); self.assertEqual(kept['readalong_on_phone'], 'Download/story.readalong.zip')
        self.assertNotIn('SECRETSERIAL', json.dumps(android_app.status(self.root, runner=runner('SECRETSERIAL\tdevice\n'))))

    def test_newer_release_is_noticed_downloaded_and_used(self):
        android_app.download(self.root, opener(self.files()))
        newer = b'PK-newer'; base = BASE.replace('v9.9.9', 'v9.10.0'); files = {
            android_app.LATEST_API: json.dumps({'tag_name': 'v9.10.0', 'assets': [
                {'name': 'PageCast-9.10.0.apk', 'browser_download_url': base + 'PageCast-9.10.0.apk'},
                {'name': 'SHA256SUMS', 'browser_download_url': base + 'SHA256SUMS'}]}).encode(),
            base + 'PageCast-9.10.0.apk': newer, base + 'SHA256SUMS': (hashlib.sha256(newer).hexdigest() + '  PageCast-9.10.0.apk\n').encode()}
        calls = []
        def run(args):
            calls.append(args)
            if args[0] == 'devices': return 0, 'List of devices attached\nA1\tdevice\n'
            if 'pm' in args: return 0, 'package:com.geminireader\n'
            if 'dumpsys' in args: return 0, '    versionName=9.9.9\n'
            if 'install' in args: return 0, 'Success'
            return 0, ''
        seen = android_app.status(self.root, runner=run, opener=opener(files))
        self.assertEqual(seen['latest_release'], 'v9.10.0'); self.assertEqual(seen['installed_version'], '9.9.9'); self.assertTrue(seen['update_available'])
        self.assertEqual(android_app.download(self.root, opener(files))['version'], 'v9.10.0')
        out = android_app.install(self.root, update=True, runner=run)
        self.assertEqual(out['installed'], 'PageCast-9.10.0.apk')  # 9.10.0, not the older 9.9.9 file that sorts later by name
        offline = android_app.status(self.root, runner=run, opener=lambda *a, **k: (_ for _ in ()).throw(OSError('offline')))
        self.assertFalse(offline['latest_release_checked']); self.assertFalse(offline['update_available'])

    def test_refused_install_is_reported_not_hidden(self):
        android_app.download(self.root, opener(self.files()))
        def run(args):
            if args[0] == 'devices': return 0, 'List of devices attached\nA1\tdevice\n'
            if 'install' in args: return 1, 'Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]'
            return 0, ''
        with self.assertRaises(ValueError) as caught: android_app.install(self.root, runner=run)
        self.assertIn('INSTALL_FAILED_UPDATE_INCOMPATIBLE', str(caught.exception))

    def test_tools_registered_and_install_asks_first(self):
        self.assertIn('pagecast_android_app', package.TOOLS); self.assertIn('pagecast_android_install', package.TOOLS)
        self.assertEqual(package.on_pre_tool_call('pagecast_android_install')['action'], 'approve')
        self.assertIsNone(package.on_pre_tool_call('pagecast_export'))


if __name__ == '__main__': unittest.main()

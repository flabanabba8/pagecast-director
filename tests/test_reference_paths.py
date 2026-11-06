import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('reference_guard_fixture', Path(__file__).parents[1]/'reference_paths.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class ReferenceTests(unittest.TestCase):
    def test_private_paths_rejected_and_profile_media_allowed(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            base = Path(tmp)
            profile = base/'custom-profile'
            plugin = profile/'plugin-data'/'example-plugin'
            plugin.mkdir(parents=True)
            external = base/'reference.wav'
            external.write_bytes(b'fixture')
            self.assertEqual(core.resolve_reference(str(external), plugin), external)
            private = base/'.codex'
            private.mkdir()
            secret = private/'reference.wav'
            secret.write_bytes(b'fixture')
            with self.assertRaisesRegex(ValueError, 'Private configuration'):
                core.resolve_reference(str(secret), plugin)
            profile_secret = profile/'reference.wav'
            profile_secret.write_bytes(b'fixture')
            with self.assertRaisesRegex(ValueError, 'private profile'):
                core.resolve_reference(str(profile_secret), plugin)
            sibling = profile/'plugin-data'/'other-plugin'
            sibling.mkdir()
            media = sibling/'reference.wav'
            media.write_bytes(b'fixture')
            self.assertEqual(core.resolve_reference(str(media), plugin), media)
            link = base/'link.wav'
            link.symlink_to(external)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                core.resolve_reference(str(link), plugin)

if __name__ == '__main__': unittest.main()

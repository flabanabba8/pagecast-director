import math
import unittest
import test_host_speech as fixture

Books = fixture.Books
package = fixture.package


class SetupTests(unittest.TestCase):
    setUp = fixture.HostSpeechTests.setUp
    tearDown = fixture.HostSpeechTests.tearDown

    def test_first_run_persistence_zero_budget_and_no_provider_call(self):
        app = Books(self.root / 'profile', speech_dispatch=lambda *_: self.fail('Setup invoked speech'))
        self.assertTrue(app.setup()['setup_required'])
        answers = dict(local_resources='CPU only; cached Kitten Nano', remote_resources='none',
                       subscriptions='user reported', api_credits='none verified',
                       max_usd_per_book=0, max_usd_per_month=0, allow_remote_text=False,
                       priority='cost', selected_backend='KittenTTS legacy Nano, runtime to verify')
        self.assertFalse(app.setup(answers)['setup_required'])
        self.assertEqual(Books(self.root / 'profile').setup()['preferences'], answers)
        for bad in (-1, math.inf, math.nan, True):
            with self.assertRaises(ValueError): app.setup({**answers, 'max_usd_per_month': bad})
        self.assertEqual(app.setup()['preferences'], answers)
        self.assertIn('pagecast_setup', package.TOOLS)
        self.assertIn('setup_required', package.invoke('pagecast_setup', {}, storage_root=self.root / 'profile'))


if __name__ == '__main__': unittest.main()

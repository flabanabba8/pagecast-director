import json
import unittest
import test_host_speech as fixture


class KnowledgeTests(unittest.TestCase):
    setUp = fixture.HostSpeechTests.setUp
    tearDown = fixture.HostSpeechTests.tearDown

    def test_packaged_topics_are_bounded_and_require_no_profile_or_backend(self):
        storage=self.root/'no-profile'
        for topic in fixture.package.knowledge.TOPICS:
            result=json.loads(fixture.package.invoke('pagecast_knowledge',{'topic':topic,'limit':200},storage_root=storage))
            self.assertEqual(len(result['sha256']),64)
            self.assertLessEqual(len(result['text']),200)
            if result['next_offset'] is not None:
                second=fixture.package.knowledge.read(topic,result['next_offset'],200)
                self.assertEqual(second['offset'],200)
        self.assertFalse(storage.exists())
        for args in ({'topic':'../../README'}, {'offset':True}, {'limit':12001}):
            self.assertIn('error',json.loads(fixture.package.invoke('pagecast_knowledge',args,storage_root=storage)))
        providers=fixture.package.knowledge.read('providers',limit=12000)['text']
        for label in ('KittenTTS','Kokoro','Inworld','OpenAI','Android','Groq'):
            self.assertIn(label,providers)

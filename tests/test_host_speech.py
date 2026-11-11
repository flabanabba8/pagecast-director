import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('pagecast_host_fixture',ROOT/'__init__.py',submodule_search_locations=[str(ROOT)])
package=importlib.util.module_from_spec(spec);sys.modules[spec.name]=package;spec.loader.exec_module(package)
Books=package.Books;host=sys.modules['pagecast_host_fixture.host_speech']

def settings(revision='one'):
    return {'host_tts_tool':'chosen_speech','host_tts_backend_id':'selected/runtime/model@'+revision,'host_tts_model':'any-selected-model','host_tts_arguments':{'input':'{text}','voice':'{voice}','model':'{model}'}}

class HostSpeechTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.wav=self.root/'provider.wav'
        with wave.open(str(self.wav),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\0\0'*4800)
    def tearDown(self):self.tmp.cleanup()
    def test_model_runtime_tool_selection_and_cache_identity(self):
        calls=[]
        def dispatch(name,args):calls.append((name,args));return {'path':str(self.wav),'credit':'Fixture speech attribution'}
        app=Books(self.root/'book',settings(),dispatch);ident=app.import_book(text='Say literal {voice} today.')['book_id'];app.set_voice(ident,'Narrator',engine='host',voice='selected-voice')
        with patch('pagecast_host_fixture.books.shutil.which',return_value=None):
            result=app.render(ident);self.assertEqual(result['generated'],1,result)
            result=app.render(ident);self.assertEqual(result['reused'],1,result)
            exported=app.export(ident,'wav')
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'chosen_speech');self.assertEqual(calls[0][1]['input'],'Say literal {voice} today.');self.assertEqual(calls[0][1]['model'],'any-selected-model')
        self.assertIn('Fixture speech attribution',exported['credit'])
        other=Books(self.root/'book',settings('two'),dispatch);self.assertNotEqual(app.plan(ident)[1][0]['signature'],other.plan(ident)[1][0]['signature'])
    def test_uncertain_failure_cannot_reroll_or_fallback(self):
        calls=[]
        def dispatch(*args):calls.append(1);raise RuntimeError('test credential must not be echoed')
        app=Books(self.root/'book',settings(),dispatch);ident=app.import_book(text='Original fixture sentence.')['book_id'];app.set_voice(ident,'Narrator',engine='host')
        self.assertEqual(app.render(ident)['state'],'failed');second=app.render(ident)
        self.assertEqual(second['state'],'failed');self.assertEqual(len(calls),1);self.assertNotIn('test credential',str(second))
    def test_approval_refusal_and_missing_selection_are_not_success(self):
        events=[]
        with self.assertRaisesRegex(RuntimeError,'refused'):
            host.synthesize(settings(),lambda *_:{'status':'denied'},'Hello','voice',self.root,lambda s,m:events.append(s))
        self.assertEqual(events,['pending','rejected'])
        with self.assertRaises(ValueError):host.binding({})
        with self.assertRaisesRegex(ValueError,'credentials'):
            cfg=settings();cfg['host_tts_arguments']['api_key']='fixture';host.binding(cfg)

if __name__=='__main__':unittest.main()

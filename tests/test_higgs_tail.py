from array import array
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch
from test_pagecast import ROOT
from pagecast_test import books as module
from pagecast_test import higgs
from pagecast_test.books import Books,trim_higgs_padding


def wav_bytes(samples):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(array('h',samples).tobytes())
    return out.getvalue()

class HiggsTailTests(unittest.TestCase):
    def test_only_long_near_silent_tail_is_removed_and_speech_bytes_preserved(self):
        speech=[1000,-1000]*12000
        internal=[0]*60000
        tail=([0]*2390+[100]*10)*30
        samples=speech+internal+speech+tail
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            p=Path(tmp)/'one.wav';p.write_bytes(wav_bytes(samples));result=trim_higgs_padding(p)
            self.assertIsNotNone(result)
            with wave.open(str(p),'rb') as w:actual=w.readframes(w.getnframes())
            self.assertEqual(actual,array('h',samples).tobytes()[:len(actual)])
            self.assertGreaterEqual(len(actual)//2,len(speech)+len(internal)+len(speech))
            self.assertAlmostEqual(result['removed_seconds'],2.7)
            p.write_bytes(wav_bytes(speech+[0]*72000+[115]*960));result=trim_higgs_padding(p);self.assertAlmostEqual(result['retained_seconds'],1.3)
            p.write_bytes(wav_bytes(speech+[-55]*1920000));result=trim_higgs_padding(p);self.assertAlmostEqual(result['retained_seconds'],1.3)
            for data in ([0]*24000,speech+[0]*12000,speech+[48,-48]*36000):
                p.write_bytes(wav_bytes(data));before=p.read_bytes();self.assertIsNone(trim_higgs_padding(p));self.assertEqual(p.read_bytes(),before)

    def test_banned_controls_are_rejected_before_network_access(self):
        for tag in higgs.BANNED_CONTROLS:
            with patch.object(higgs,'build_opener') as network,self.assertRaises(ValueError):higgs.synthesize('http://localhost:8000','fixture',tag+' Hello.','default')
            network.assert_not_called()

    def test_long_higgs_tail_is_recovered_without_speech_retry_and_raw_take_archived(self):
        raw=wav_bytes([1000,-1000]*12000+[0]*1920000)
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp,patch.object(module,'synthesize',return_value=raw) as speak:
            b=Books(tmp);identifier=b.import_book(text='Hello.')['book_id'];b.set_voice(identifier,'Narrator',engine='higgs')
            result=b.render(identifier);self.assertEqual(result['state'],'complete',result);self.assertEqual(speak.call_count,1)
            _,rows,_=b.plan(identifier);receipt=json.loads((Path(rows[0]['audio_path']).parent/'receipt.json').read_text())
            self.assertAlmostEqual(receipt['seconds'],1.3);self.assertIn('higgs_trailing_padding',receipt['postprocessing'])
            archives=list((b.folder(identifier)/'archive').glob('*.wav'));self.assertEqual(len(archives),1);self.assertEqual(archives[0].read_bytes(),raw)
            self.assertEqual(b.render(identifier)['generated'],0);self.assertEqual(speak.call_count,1)

if __name__=='__main__':unittest.main()

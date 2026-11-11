import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from test_pagecast import ROOT


class ServerTests(unittest.TestCase):
    def test_actual_stdio_protocol_and_shared_tools_without_hermes_or_llm_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            env={k:v for k,v in os.environ.items() if not any(s in k for s in ('API_KEY','TOKEN','SECRET','HERMES'))}
            p=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--data-dir',tmp],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            def call(identifier,method,params=None):
                p.stdin.write(json.dumps({'jsonrpc':'2.0','id':identifier,'method':method,'params':params or {}})+'\n');p.stdin.flush()
                result=json.loads(p.stdout.readline());self.assertEqual(result['id'],identifier);return result['result']
            try:
                initialized=call(1,'initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'fixture','version':'1'}})
                self.assertEqual(initialized['protocolVersion'],'2025-03-26')
                self.assertIn('LLM wiki',initialized['instructions'])
                knowledge=call(10,'tools/call',{'name':'pagecast_knowledge','arguments':{'topic':'providers','limit':12000}})
                self.assertIn('KittenTTS',json.loads(knowledge['content'][0]['text'])['text'])
                listed=call(2,'tools/list')['tools'];self.assertIn('pagecast_overview',[t['name'] for t in listed])
                imported=call(3,'tools/call',{'name':'pagecast_import','arguments':{'text':'An original fixture line.'}})
                identifier=json.loads(imported['content'][0]['text'])['book_id']
                overview=call(4,'tools/call',{'name':'pagecast_overview','arguments':{'book_id':identifier}})
                safe=json.loads(overview['content'][0]['text']);self.assertNotIn('passages',safe);self.assertTrue(safe['spoiler_safe'])
                invalid=call(5,'tools/call',{'name':'pagecast__export','arguments':{'book_id':identifier}})
                self.assertTrue(invalid['isError'])
            finally:
                p.stdin.close();p.wait(timeout=10);self.assertEqual(p.returncode,0,p.stderr.read());p.stdout.close();p.stderr.close()

if __name__=='__main__':unittest.main()

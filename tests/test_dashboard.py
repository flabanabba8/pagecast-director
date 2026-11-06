import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    FastAPI = None


@unittest.skipUnless(FastAPI, 'Run with Hermes runtime for route checks')
class Dashboard(unittest.TestCase):
    def test_settings_scoped_route(self):
        path = Path(__file__).resolve().parents[1] / 'dashboard/plugin_api.py'
        spec = importlib.util.spec_from_file_location('pagecast_dashboard_test', path)
        mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
        app = FastAPI(); app.include_router(mod.router)
        settings = {'inworld_model': 'inworld-tts-2-flash'}
        with TestClient(app) as client, patch('hermes_cli.config.load_config', return_value={'plugins': {'entries': {'pagecast-director': {'settings': settings}}}}), patch.object(mod.package, 'invoke', return_value=json.dumps({'books': []})) as invoke:
            self.assertEqual(client.post('/action', json={'operation': 'pagecast_books'}).status_code, 200)
            invoke.assert_called_once_with('pagecast_books', {}, settings)
            self.assertEqual(client.post('/action', json={'operation': 'terminal'}).status_code, 400)

    def test_inworld_secret_is_profile_scoped(self):
        from agent.secret_scope import set_multiplex_context, reset_multiplex_context, set_secret_scope, reset_secret_scope
        from test_pagecast import package
        mode = set_multiplex_context(True)
        try:
            first = set_secret_scope({'INWORLD_API_KEY': 'Basic Zmlyc3Q6Zml4dHVyZQ=='})
            try: self.assertEqual(package.inworld.credential(), 'Zmlyc3Q6Zml4dHVyZQ==')
            finally: reset_secret_scope(first)
            second = set_secret_scope({})
            try:
                with self.assertRaises(ValueError): package.inworld.credential()
            finally: reset_secret_scope(second)
        finally: reset_multiplex_context(mode)

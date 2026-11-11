#!/usr/bin/env python3
"""Local MCP/CLI adapter. No LLM client, subscription token access or Hermes dependency."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pagecast_runtime', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from pagecast_runtime.credentials import standalone


def execute(name, arguments, storage, settings):
    with standalone():
        return json.loads(package.invoke(name, arguments, settings, storage_root=storage, source="mcp"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('PAGECAST_DATA_DIR', str(Path.home() / '.local/share/pagecast-director'))))
    parser.add_argument('--settings', type=Path, help='Explicit local JSON settings file; never put speech keys or harness tokens here')
    parser.add_argument('--call', choices=list(package.TOOLS))
    parser.add_argument('--arguments-file', type=Path)
    parser.add_argument('--list-tools', action='store_true')
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text()) if args.settings else {}
    if not isinstance(settings, dict): parser.error('Settings must be an object')
    if os.environ.get('PAGECAST_INWORLD_MODEL'): settings['inworld_model'] = os.environ['PAGECAST_INWORLD_MODEL']
    tools = [{'name': name, 'description': description, 'inputSchema': {'type': 'object', 'properties': fields, 'required': required, 'additionalProperties': False}}
             for name, (description, fields, required) in package.TOOLS.items()]
    if args.list_tools: print(json.dumps({'tools': tools})); return
    if args.call:
        arguments = json.loads(args.arguments_file.read_text()) if args.arguments_file else json.load(sys.stdin)
        print(json.dumps(execute(args.call, arguments, args.data_dir, settings))); return
    output_lock, active_lock = threading.Lock(), threading.Lock()
    active = {}
    def send(value):
        with output_lock:
            sys.stdout.write(json.dumps(value, ensure_ascii=True) + '\n'); sys.stdout.flush()
    def handle(message):
        identifier = message.get('id')
        method, params = message.get('method'), message.get('params', {})
        if identifier is None: return
        try:
            if method == 'initialize':
                version = params.get('protocolVersion')
                if version not in ('2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25'): version = '2025-03-26'
                result = {'protocolVersion': version, 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'pagecast-director', 'version': '0.2.0'},
                          'instructions': 'Use your CURRENT harness model for all LLM analysis, casting and direction. No separate LLM API is used. Keep normal replies spoiler-free. Before speech setup read pagecast_knowledge index, then relevant topics, and pagecast_setup. Knowledge is not installed backend support.\n\n' + package.knowledge.read('index', limit=12000)['text']}
            elif method == 'ping': result = {}
            elif method == 'tools/list': result = {'tools': tools}
            elif method == 'tools/call':
                name, arguments = params.get('name'), params.get('arguments', {})
                if name == 'pagecast_render':
                    with active_lock: active[identifier] = arguments.get('book_id')
                value = execute(name, arguments, args.data_dir, settings)
                result = {'content': [{'type': 'text', 'text': json.dumps(value)}], 'isError': 'error' in value}
            else:
                send({'jsonrpc': '2.0', 'id': identifier, 'error': {'code': -32601, 'message': 'Method not found'}}); return
            send({'jsonrpc': '2.0', 'id': identifier, 'result': result})
        except Exception:
            # Do not echo request arguments, source text or credential-bearing exceptions.
            send({'jsonrpc': '2.0', 'id': identifier, 'error': {'code': -32603, 'message': 'PageCast request failed'}})
        finally:
            with active_lock: active.pop(identifier, None)
    # Bounded concurrency lets cancellation/progress calls run while speech is in flight.
    with ThreadPoolExecutor(max_workers=4) as workers:
        while True:
            line = sys.stdin.buffer.readline(8 * 1024 * 1024 + 1)
            if not line: break
            if len(line) > 8 * 1024 * 1024:
                send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Request exceeds limit'}}); break
            try: message = json.loads(line)
            except (ValueError, UnicodeError):
                send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON'}}); continue
            if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('params', {}), dict):
                send({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}}); continue
            if message.get('method') == 'notifications/cancelled':
                with active_lock: book = active.get(message['params'].get('requestId'))
                if book: execute('pagecast_cancel', {'book_id': book}, args.data_dir, settings)
            else: workers.submit(handle, message)
        with active_lock: books = list(active.values())
        for book in books:
            if book: execute('pagecast_cancel', {'book_id': book}, args.data_dir, settings)


if __name__ == '__main__': main()

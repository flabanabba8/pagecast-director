#!/usr/bin/env python3
"""Print an OpenCode v2 MCP config fragment with resolved paths; never modify user config."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
print(json.dumps({'$schema': 'https://opencode.ai/config.json', 'mcp': {'servers': {'pagecast-director': {
    'type': 'local', 'command': [sys.executable, str(root / 'server.py')]
}}}}, indent=2))

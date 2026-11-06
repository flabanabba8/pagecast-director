"""Resolve user-selected references without reading credential directories."""
from pathlib import Path

PRIVATE = {'.ssh', '.gnupg', '.aws', '.azure', '.codex', '.docker', '.kube', '.pki', '.config'}


def resolve_reference(value, plugin_root):
    path = Path(value).expanduser()
    if path.is_symlink() or any(x in PRIVATE for x in path.parts):
        raise ValueError('Private configuration paths and symlink references are unsupported')
    resolved = path.resolve(strict=True)
    if any(x in PRIVATE for x in resolved.parts):
        raise ValueError('Private configuration paths are unsupported')
    root = Path(plugin_root).resolve()
    data_root = root.parent if root.parent.name == 'plugin-data' else None
    profile_home = data_root.parent if data_root is not None else None
    protected = '.hermes' in path.parts or '.hermes' in resolved.parts or (profile_home is not None and resolved.is_relative_to(profile_home))
    if protected and (data_root is None or not resolved.is_relative_to(data_root)):
        raise ValueError('Reference cannot come from private profile configuration')
    return resolved

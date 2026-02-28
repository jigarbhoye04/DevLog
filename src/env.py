"""
Pure-Python .env file loader.
Loads KEY=VALUE pairs from a .env file without any external dependencies.
Searches for .env.local, then .env, starting from the directory of this file
upward to the repo root.
"""
from pathlib import Path


def _find_env_file() -> Path | None:
    """Walk up the directory tree to find a .env.local or .env file."""
    candidates = [".env.local", ".env"]
    # Start from the src/ dir's parent (repo root)
    search = Path(__file__).parent.parent
    for name in candidates:
        target = search / name
        if target.exists():
            return target
    return None


def _parse_env_file(path: Path) -> dict:
    """Parse KEY=VALUE lines from a file, handling quoted values."""
    result = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, raw_value = line.partition('=')
            key = key.strip()
            value = raw_value.strip().strip('"').strip("'")
            result[key] = value
    return result


# Module-level cache so we only parse once per process
_cache: dict | None = None


def load() -> dict:
    """Returns the parsed env vars. Cached after first call."""
    global _cache
    if _cache is not None:
        return _cache

    env_file = _find_env_file()
    _cache = _parse_env_file(env_file) if env_file else {}
    return _cache


def get(key: str, default: str = "") -> str:
    """Get a single env var, checking os.environ first, then .env.local."""
    import os
    return os.environ.get(key) or load().get(key, default)

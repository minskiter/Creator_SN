"""Shared PostgreSQL configuration; importing this module never opens a connection."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BACKEND_DIR / 'api/app_config.json'


def build_db_url() -> str:
    url = os.environ.get('DATABASE_URL')
    if not url:
        with CONFIG_PATH.open(encoding='utf-8') as stream:
            url = json.load(stream).get('database_url')
    if not url:
        raise ValueError('Set DATABASE_URL or database_url in backend/api/app_config.json; SQLite fallback is disabled.')
    parsed = urlsplit(url)
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname or not parsed.path.strip('/'):
        raise ValueError('Database must be a PostgreSQL URL with a hostname and database name.')
    if parsed.query or parsed.fragment:
        raise ValueError('Database URL query parameters/fragments are not supported; use a dedicated public schema database.')
    return url


def tortoise_config() -> dict:
    return {
        'connections': {'default': build_db_url()},
        'apps': {'models': {'models': ['api.models.db_models'], 'default_connection': 'default'}},
        'use_tz': True,
        'timezone': 'UTC',
    }

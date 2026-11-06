"""Atomic PostgreSQL custom-format backups (never copies a live SQLite file)."""
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

from api.models.database import BACKEND_DIR, build_db_url

BACKUP_DIR = BACKEND_DIR / 'backup'
BACKUP_INTERVAL_DAYS = 30


def pg_dump_binary():
    explicit = os.environ.get('PG_DUMP_BIN')
    if explicit:
        return explicit
    found = shutil.which('pg_dump')
    if found:
        return found
    homebrew = Path('/opt/homebrew/opt/postgresql@18/bin/pg_dump')
    if homebrew.is_file():
        return str(homebrew)
    raise RuntimeError('pg_dump is required for PostgreSQL backups; set PG_DUMP_BIN.')


def create_monthly_db_backup(*, force=False):
    today = datetime.date.today()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dates = []
    for child in BACKUP_DIR.glob('db_*'):
        if child.is_dir() and (child / 'database.dump').is_file():
            try:
                dates.append(datetime.datetime.strptime(child.name[:13], 'db_%Y_%m_%d').date())
            except ValueError:
                pass
    if not force and dates and (today-max(dates)).days < BACKUP_INTERVAL_DAYS:
        return None
    target = BACKUP_DIR / f'db_{today:%Y_%m_%d}'
    # Do not overwrite an existing SQLite backup or completed PostgreSQL backup.
    if target.exists():
        target = BACKUP_DIR / f'db_{today:%Y_%m_%d}_{datetime.datetime.now():%H%M%S_%f}'
    parsed = urlsplit(build_db_url())
    env = os.environ.copy()
    env.update(PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432),
               PGUSER=unquote(parsed.username or ''), PGPASSWORD=unquote(parsed.password or ''),
               PGDATABASE=unquote(parsed.path.lstrip('/')), PGCONNECT_TIMEOUT='10')
    temporary = Path(tempfile.mkdtemp(prefix='.postgres-backup-',dir=BACKUP_DIR))
    try:
        process = subprocess.run([pg_dump_binary(), '--format=custom', '--no-owner', '--no-acl',
                                  '--file', str(temporary / 'database.dump')], env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if process.returncode:
            # Do not echo client diagnostics that might contain connection credentials.
            raise RuntimeError('pg_dump failed; verify connectivity and use a client version >= server version.')
        (temporary / 'database.dump').chmod(0o600)
        temporary.rename(target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(f'PostgreSQL backup created: {target}')
    return target

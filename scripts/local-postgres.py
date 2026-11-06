"""Manage this checkout's isolated, password-protected PostgreSQL cluster."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
DATA = LOCAL / 'postgres'
SOCKET = LOCAL / 'pgsocket'
PORT = 55432


def binaries():
    directory = os.environ.get('PG_BIN')
    if not directory:
        found = shutil.which('pg_ctl')
        directory = str(Path(found).parent) if found else '/opt/homebrew/opt/postgresql@18/bin'
    result = Path(directory)
    if not (result / 'pg_ctl').is_file():
        sys.exit('PostgreSQL server tools missing. Install postgresql@18 or set PG_BIN.')
    return result


def secret(name):
    path = LOCAL / name
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return path.read_text().strip()
    password = secrets.token_urlsafe(32)
    with os.fdopen(fd, 'w') as stream:
        stream.write(password + '\n')
    return password


async def provision():
    import asyncpg
    connection = await asyncpg.connect(host='127.0.0.1', port=PORT, user='creator_admin',
                                      password=secret('postgres-admin-password'), database='postgres', timeout=10)
    try:
        password = secret('postgres-app-password')
        if not await connection.fetchval("SELECT 1 FROM pg_roles WHERE rolname='creatorsn'"):
            await connection.execute("CREATE ROLE creatorsn LOGIN PASSWORD '" + password.replace("'", "''") + "'")
        if not await connection.fetchval("SELECT 1 FROM pg_database WHERE datname='creatorsn_dev'"):
            await connection.execute('CREATE DATABASE creatorsn_dev OWNER creatorsn')
    finally:
        await connection.close()
    path = ROOT / 'backend/api/app_config.json'
    config = json.loads(path.read_text())
    if not config.get('database_url'):
        config['database_url'] = f'postgres://creatorsn:{quote(password, safe="")}@127.0.0.1:{PORT}/creatorsn_dev'
        tmp = path.with_suffix('.json.tmp')
        fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(config, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(tmp, path)
    print('Local PostgreSQL ready: 127.0.0.1:55432 / creatorsn_dev (credentials not displayed).')


def main(action):
    bin_dir = binaries()
    pg_ctl = str(bin_dir / 'pg_ctl')
    if action in ('status', 'stop'):
        if not (DATA / 'PG_VERSION').exists():
            sys.exit('This checkout has no initialized PostgreSQL cluster.')
        cmd = [pg_ctl, '-D', str(DATA), action]
        if action == 'stop':
            cmd += ['-m', 'fast', '-w']
        return subprocess.call(cmd)
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    SOCKET.mkdir(exist_ok=True, mode=0o700)
    running = subprocess.run([pg_ctl, '-D', str(DATA), 'status'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not running:
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', PORT))
            except OSError:
                sys.exit('Port 55432 is occupied; no existing service was changed.')
    if not (DATA / 'PG_VERSION').exists():
        secret('postgres-admin-password')
        subprocess.run([str(bin_dir / 'initdb'), '-D', str(DATA), '-U', 'creator_admin',
                        '--pwfile', str(LOCAL / 'postgres-admin-password'), '--auth-host=scram-sha-256',
                        '--auth-local=scram-sha-256', '--encoding=UTF8', '--locale=C'], check=True)
    if not running:
        subprocess.run([pg_ctl, '-D', str(DATA), '-l', str(LOCAL / 'postgres.log'), '-w',
                        '-o', f'-h 127.0.0.1 -p {PORT} -k {SOCKET}', 'start'], check=True)
    asyncio.run(provision())
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status'], default='start', nargs='?')
    try:
        sys.exit(main(parser.parse_args().action))
    except Exception as exc:
        sys.exit(f'Local PostgreSQL operation failed ({type(exc).__name__}); see .local/postgres.log. No credentials printed.')

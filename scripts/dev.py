"""Run both development servers; Ctrl+C stops only the processes started here."""
import os
import json
from urllib.parse import urlsplit
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
python = root / '.venv/bin/python'
node = shutil.which('node')
vite = root / 'ui/node_modules/vite/bin/vite.js'
if not python.exists() or not node or not vite.exists():
    sys.exit('Dependencies missing. Run ./scripts/setup-dev.sh first.')
if not (root / 'backend/api/app_config.json').exists():
    sys.exit('Configuration missing. Run ./scripts/setup-dev.sh first.')
for port in (8000, 8080):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            sys.exit(f'Port {port} is busy; no existing process was stopped.')

# Start only this checkout's own local cluster. Never auto-upgrade remote DBs.
config = json.loads((root / 'backend/api/app_config.json').read_text())
database_url = os.environ.get('DATABASE_URL') or config.get('database_url', '')
address = urlsplit(database_url)
is_local = address.hostname in ('127.0.0.1', 'localhost', '::1')
if is_local and address.port == 55432 and address.path == '/creatorsn_dev':
    subprocess.run([str(python), str(root / 'scripts/local-postgres.py'), 'start'], cwd=root, check=True)
command = [str(python), str(root / 'backend/scripts/init_database.py')]
if not is_local:
    command.append('--check')
subprocess.run(command, cwd=root, check=True)

processes = []

def stop(signum, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, stop)
try:
    processes.append(subprocess.Popen(
        [str(python), '-m', 'uvicorn', 'app:app', '--reload', '--host', '127.0.0.1', '--port', '8000'],
        cwd=root / 'backend', start_new_session=True))
    processes.append(subprocess.Popen(
        [node, str(vite), '--host', '127.0.0.1', '--port', '8080', '--strictPort'],
        cwd=root / 'ui', start_new_session=True))
    print('Frontend: http://127.0.0.1:8080  API docs: http://127.0.0.1:8000/docs', flush=True)
    while all(process.poll() is None for process in processes):
        time.sleep(0.5)
    sys.exit('A development server exited. See output above.')
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for process in processes:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

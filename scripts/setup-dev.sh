#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3.13}"
command -v "$PYTHON" >/dev/null || { echo 'Install Python 3.13 or set PYTHON to its executable.'; exit 1; }
node -e 'if (Number(process.versions.node.split(".")[0]) !== 22) { console.error("Use Node.js 22 (see .nvmrc)"); process.exit(1) }'
[ -d .venv ] || "$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.lock.txt
npm --prefix ui ci
.venv/bin/python scripts/init-dev.py
.venv/bin/python scripts/local-postgres.py start
# This setup command is local-only: never apply DDL to an inherited remote URL.
PYTHONPATH=backend .venv/bin/python - <<'CHECK'
from urllib.parse import urlsplit
from api.models.database import build_db_url
if urlsplit(build_db_url()).hostname not in ('127.0.0.1', 'localhost', '::1'):
    raise SystemExit('Refusing automatic remote database upgrade. Run the reviewed database script explicitly instead.')
CHECK
.venv/bin/python backend/scripts/init_database.py
echo 'Ready. Start: .venv/bin/python scripts/dev.py'

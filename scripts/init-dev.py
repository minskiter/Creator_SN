"""Create local-only credentials without overwriting an existing configuration."""
import json
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
path = root / 'backend/api/app_config.json'
config = {
    'root_name': 'admin',
    'root_pwd': secrets.token_urlsafe(18),
    'invite_code': secrets.token_urlsafe(18),
    'jwt_key': secrets.token_urlsafe(48),
    'allow_origins': ['http://127.0.0.1:8080', 'http://localhost:8080'],
}
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Existing backend configuration preserved.')
else:
    with os.fdopen(fd, 'w') as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print('Created backend/api/app_config.json (local credentials; mode 0600).')

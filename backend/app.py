import asyncio
import contextlib
import json
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from tortoise.contrib.fastapi import register_tortoise

from api.controllers.member import router as member_router
from api.controllers.product import router as product_router
from api.controllers.project import router as project_router, seed_default_projects
from api.controllers.resume import router as resume_router
from api.controllers.user import router as user_router
from api.controllers.oidc import router as oidc_router
from api.models.db_backup import create_monthly_db_backup
from api.models.database import tortoise_config


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'static'
CONFIG_PATH = BASE_DIR / 'api' / 'app_config.json'
with CONFIG_PATH.open(encoding='utf-8') as config_file:
    app_config = json.load(config_file)

app = FastAPI(title='Creator SN Backend', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.get('allow_origins', ['*']),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware('http')
async def api_compatibility_prefix(request: Request, call_next):
    """Keep the frontend's /api URLs compatible with the existing API routes."""
    if request.scope['path'] == '/api' or request.scope['path'].startswith('/api/'):
        request.scope['path'] = request.scope['path'][4:] or '/'
    path = request.scope['path']
    public_oidc = path in {
        '/oauth/token', '/oauth/userinfo', '/oauth/revoke',
        '/oauth/jwks', '/.well-known/openid-configuration',
    }
    if public_oidc and request.method == 'OPTIONS':
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    if path.startswith(('/oauth/', '/oidc/')):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
    if public_oidc:
        # These routes use explicit OAuth credentials, never cookies/session auth.
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        if 'access-control-allow-credentials' in response.headers:
            del response.headers['access-control-allow-credentials']
    return response

BACKUP_CHECK_SECONDS = 30 * 24 * 60 * 60
backup_task = None

register_tortoise(
    app,
    config=tortoise_config(),
    generate_schemas=False,
    add_exception_handlers=True,
)


async def periodic_db_backup():
    while True:
        await asyncio.sleep(BACKUP_CHECK_SECONDS)
        try:
            await asyncio.to_thread(create_monthly_db_backup)
        except Exception as exc:
            print(f'Database backup failed: {exc}')


@app.on_event('startup')
async def startup():
    global backup_task
    await seed_default_projects()
    backup_task = asyncio.create_task(periodic_db_backup())


@app.on_event('shutdown')
async def shutdown():
    if backup_task is not None:
        backup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await backup_task


app.include_router(user_router)
app.include_router(member_router)
app.include_router(product_router)
app.include_router(project_router)
app.include_router(resume_router)
app.include_router(oidc_router)

# The frontend is built into this directory by the multi-stage Dockerfile.
# html=True also serves index.html for the root document; the Vue app uses hash
# history, so client-side routes do not require additional server rewrites.
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='frontend')

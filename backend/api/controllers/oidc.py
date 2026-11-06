"""Authorization-code OIDC provider; no dynamic registration or password grant."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode, unquote_plus

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from tortoise.transactions import in_transaction

from api.models.database import CONFIG_PATH
from api.models.db_models import OIDCClient, OIDCCode, OIDCAccessToken, UserDBModel
from api.models.jwt_tool import decode_jwt
from api.models.verify_tool import Auth
from api.models.oidc import (
    b64, check_secret, digest, encode_id_token, get_signer, hash_secret, settings, valid_redirect,
)

router = APIRouter(tags=['OIDC'])
config = json.loads(CONFIG_PATH.read_text())
auth = Auth(config)
SCOPES = {'openid', 'profile', 'email'}


def fail(error, status=400):
    raise HTTPException(status, detail=error)


def ready():
    try:
        get_signer()
    except (OSError, ValueError):
        fail('OIDC signing key has not been provisioned', 503)


async def current_user(api_key: str = Header(None)):
    claims = decode_jwt(api_key, config['jwt_key']) if api_key else {}
    userid = claims.get('userid')
    if not userid or not isinstance(claims.get('exp'), (int, float)):
        fail('Login required', 401)
    if userid != config['root_name'] and not await UserDBModel.filter(userid=userid).exists():
        fail('Login required', 401)
    return {**claims, 'auth_time': int(claims.get('iat', claims['exp'] - 14 * 86400))}


async def admin(user=Depends(current_user)):
    if not await auth.current_admin(user):
        fail('Administrator account required', 403)
    return user


class ClientInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=2000)
    redirect_uris: list[str] = Field(min_length=1, max_length=20)
    client_type: str = 'public'
    enabled: bool = True

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError('Application name is required')
        return value.strip()

    @field_validator('client_type')
    @classmethod
    def type_valid(cls, value):
        if value not in ('public', 'confidential'):
            raise ValueError('Expected public or confidential')
        return value

    @field_validator('redirect_uris')
    @classmethod
    def redirects_valid(cls, values):
        if not all(valid_redirect(value) for value in values):
            raise ValueError('Use exact HTTPS callbacks (HTTP is allowed only for loopback development)')
        return list(dict.fromkeys(values))


def client_info(client):
    return {key: getattr(client, key) for key in (
        'client_id', 'name', 'description', 'redirect_uris', 'client_type', 'enabled', 'created_at')}


@router.get('/oidc/clients')
async def clients(_=Depends(admin)):
    return [client_info(client) for client in await OIDCClient.all().order_by('-created_at')]


@router.post('/oidc/clients', status_code=201)
async def create_client(body: ClientInput, user=Depends(admin)):
    secret = secrets.token_urlsafe(32) if body.client_type == 'confidential' else None
    client = await OIDCClient.create(
        **body.model_dump(), client_id=secrets.token_urlsafe(24),
        secret_hash=hash_secret(secret) if secret else None,
        created_by=user['userid'], created_at=int(time.time()))
    return {**client_info(client), 'client_secret': secret}


@router.put('/oidc/clients/{client_id}')
async def update_client(client_id: str, body: ClientInput, _=Depends(admin)):
    async with in_transaction() as connection:
        client = await OIDCClient.filter(client_id=client_id).using_db(connection).select_for_update().first()
        if not client:
            fail('Application not found', 404)
        if client.client_type != body.client_type:
            fail('Client type is immutable; create a new application')
        client.update_from_dict(body.model_dump())
        await client.save(using_db=connection)
        # Editing registrations invalidates pending grants and current access tokens.
        await OIDCCode.filter(client_id=client_id).using_db(connection).delete()
        await OIDCAccessToken.filter(client_id=client_id).using_db(connection).delete()
    return client_info(client)


@router.delete('/oidc/clients/{client_id}', status_code=204)
async def delete_client(client_id: str, _=Depends(admin)):
    async with in_transaction() as connection:
        client = await OIDCClient.filter(client_id=client_id).using_db(connection).select_for_update().first()
        if not client:
            fail('Application not found', 404)
        await client.delete(using_db=connection)


@router.post('/oidc/clients/{client_id}/rotate-secret')
async def rotate_secret(client_id: str, _=Depends(admin)):
    async with in_transaction() as connection:
        client = await OIDCClient.filter(client_id=client_id).using_db(connection).select_for_update().first()
        if not client:
            fail('Application not found', 404)
        if client.client_type != 'confidential':
            fail('Public clients do not have a secret')
        secret = secrets.token_urlsafe(32)
        client.secret_hash = hash_secret(secret)
        await client.save(using_db=connection)
        await OIDCCode.filter(client_id=client_id).using_db(connection).delete()
        await OIDCAccessToken.filter(client_id=client_id).using_db(connection).delete()
    return {'client_id': client_id, 'client_secret': secret}


@router.get('/.well-known/openid-configuration')
async def discovery():
    ready()
    issuer, _ = settings()
    return {
        'issuer': issuer, 'authorization_endpoint': issuer + '/oauth/authorize',
        'token_endpoint': issuer + '/oauth/token', 'userinfo_endpoint': issuer + '/oauth/userinfo',
        'jwks_uri': issuer + '/oauth/jwks', 'revocation_endpoint': issuer + '/oauth/revoke',
        'response_types_supported': ['code'], 'grant_types_supported': ['authorization_code'],
        'subject_types_supported': ['public'], 'id_token_signing_alg_values_supported': ['RS256'],
        'token_endpoint_auth_methods_supported': ['none', 'client_secret_basic'],
        'revocation_endpoint_auth_methods_supported': ['none', 'client_secret_basic'],
        'scopes_supported': sorted(SCOPES), 'code_challenge_methods_supported': ['S256'],
        'claims_supported': ['sub', 'iss', 'aud', 'exp', 'iat', 'auth_time', 'nonce', 'at_hash',
                             'name', 'preferred_username', 'email', 'email_verified'],
    }


@router.get('/oauth/jwks')
async def jwks():
    ready()
    return {'keys': [get_signer()[1]]}


class AuthorizationInput(BaseModel):
    client_id: str = Field(max_length=64)
    redirect_uri: str = Field(max_length=2048)
    response_type: str = 'code'
    scope: str = Field(default='openid', max_length=64)
    state: str = Field(default='', max_length=1024)
    nonce: str | None = Field(default=None, max_length=512)
    code_challenge: str = Field(max_length=128)
    code_challenge_method: str = 'S256'
    decision: str | None = None


async def validate_authorization(body, connection=None):
    ready()
    query = OIDCClient.filter(client_id=body.client_id, enabled=True)
    if connection:
        query = query.using_db(connection).select_for_update()
    client = await query.first()
    if not client or body.redirect_uri not in client.redirect_uris:
        fail('Invalid application or callback')  # NEVER redirect to an unvalidated URI.
    if body.response_type != 'code':
        fail('unsupported_response_type')
    if not set(body.scope.split()) <= SCOPES or 'openid' not in body.scope.split():
        fail('invalid_scope')
    if body.code_challenge_method != 'S256' or not re.fullmatch(r'[A-Za-z0-9_-]{43}', body.code_challenge):
        fail('S256 PKCE is required')
    return client


def redirect_result(body, **values):
    parts = [body.redirect_uri, '&' if '?' in body.redirect_uri else '?']
    if body.state:
        values['state'] = body.state
    return ''.join(parts) + urlencode(values)


@router.get('/oauth/authorize')
async def authorize(request: Request):
    # Parse only supported parameters. Duplicate parameters are ambiguous and rejected.
    pairs = list(request.query_params.multi_items())
    if len({key for key, _ in pairs}) != len(pairs):
        fail('Duplicate authorization parameter')
    if any(key not in AuthorizationInput.model_fields or key == 'decision' for key, _ in pairs):
        fail('Unsupported authorization parameter')
    try:
        body = AuthorizationInput(**dict(pairs))
    except ValueError:
        fail('Invalid authorization request')
    await validate_authorization(body)
    return RedirectResponse(settings()[0] + '/#/oauth/authorize?' + urlencode(dict(pairs)), status_code=302,
                            headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})


@router.post('/oidc/authorize/preview')
async def preview(body: AuthorizationInput, _=Depends(current_user)):
    client = await validate_authorization(body)
    return {'name': client.name, 'description': client.description,
            'redirect_uri': body.redirect_uri, 'scopes': body.scope.split()}


@router.post('/oidc/authorize')
async def consent(body: AuthorizationInput, user=Depends(current_user)):
    async with in_transaction() as connection:
        await validate_authorization(body, connection)
        if body.decision == 'deny':
            return {'redirect_to': redirect_result(body, error='access_denied')}
        if body.decision != 'allow':
            fail('Explicit consent is required')
        code = secrets.token_urlsafe(32)
        now = int(time.time())
        # Lazy expiry cleanup; no plaintext codes/tokens are persisted.
        await OIDCCode.filter(expires_at__lte=now-900).using_db(connection).delete()
        await OIDCAccessToken.filter(expires_at__lte=now).using_db(connection).delete()
        await OIDCCode.create(using_db=connection, code_hash=digest(code), client_id=body.client_id,
                              subject=user['userid'], redirect_uri=body.redirect_uri,
                              scope=' '.join(sorted(set(body.scope.split()))), nonce=body.nonce,
                              challenge=body.code_challenge, auth_time=user['auth_time'], expires_at=now+120)
    return {'redirect_to': redirect_result(body, code=code)}


def oauth_error(error, status=400):
    return JSONResponse({'error': error}, status_code=status,
                        headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache',
                                 **({'WWW-Authenticate': 'Basic realm="OIDC"'} if status == 401 else {})})


async def form_data(request):
    # Do not read an unbounded request body or permit duplicate parameters.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 16384:
            raise ValueError('Oversized request')
    if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
        raise ValueError('Expected form encoding')
    pairs = parse_qsl(data.decode(), keep_blank_values=True, max_num_fields=20)
    if len(dict(pairs)) != len(pairs):
        raise ValueError('Duplicate parameter')
    return dict(pairs)


async def authenticated_client(request, form, connection):
    header = request.headers.get('authorization', '')
    secret = None
    basic = bool(header)
    if header:
        if not header.startswith('Basic ') or 'client_secret' in form:
            return None
        try:
            identifier, secret = base64.b64decode(header[6:], validate=True).decode().split(':', 1)
            identifier, secret = unquote_plus(identifier), unquote_plus(secret)
            if form.get('client_id') and form['client_id'] != identifier:
                return None
        except (ValueError, UnicodeError):
            return None
    else:
        identifier = form.get('client_id', '')
    client = await OIDCClient.filter(client_id=identifier, enabled=True).using_db(connection).select_for_update().first()
    if not client:
        return None
    if client.client_type == 'confidential':
        if not basic or not check_secret(secret or '', client.secret_hash):
            return None
    elif basic or 'client_secret' in form:
        return None
    return client


async def profile(subject, scope):
    user = await UserDBModel.get_or_none(userid=subject)
    if not user and subject != config['root_name']:
        return None
    claims = {'sub': subject}
    if 'profile' in scope.split():
        claims.update(name=(user.name if user else None) or subject, preferred_username=subject)
    if 'email' in scope.split() and user and user.email:
        # Existing account email addresses have not been verified.
        claims.update(email=user.email, email_verified=False)
    return claims


@router.post('/oauth/token')
async def token(request: Request):
    ready()
    try:
        form = await form_data(request)
    except (ValueError, UnicodeError):
        return oauth_error('invalid_request')
    if form.get('grant_type') != 'authorization_code':
        return oauth_error('unsupported_grant_type')
    verifier = form.get('code_verifier', '')
    if not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier):
        return oauth_error('invalid_grant')
    async with in_transaction() as connection:
        client = await authenticated_client(request, form, connection)
        if not client:
            return oauth_error('invalid_client', 401)
        code = await OIDCCode.filter(code_hash=digest(form.get('code', '')),
                                     client_id=client.client_id).using_db(connection).select_for_update().first()
        now = int(time.time())
        if code and code.consumed:
            await OIDCAccessToken.filter(grant_hash=code.code_hash).using_db(connection).delete()
            return oauth_error('invalid_grant')
        if (not code or code.expires_at <= now or code.redirect_uri != form.get('redirect_uri')
                or code.redirect_uri not in client.redirect_uris
                or not hmac.compare_digest(code.challenge, b64(hashlib.sha256(verifier.encode()).digest()))):
            return oauth_error('invalid_grant')
        claims = await profile(code.subject, code.scope)
        if claims is None:
            return oauth_error('invalid_grant')
        access = secrets.token_urlsafe(32)
        id_claims = {**claims, 'iss': settings()[0], 'aud': client.client_id,
                     'iat': now, 'exp': now+900, 'auth_time': code.auth_time,
                     'at_hash': b64(hashlib.sha256(access.encode()).digest()[:16])}
        if code.nonce is not None:
            id_claims['nonce'] = code.nonce
        signed = encode_id_token(id_claims)
        await OIDCAccessToken.create(using_db=connection, token_hash=digest(access), client_id=client.client_id,
                                     subject=code.subject, scope=code.scope, expires_at=now+900,
                                     grant_hash=code.code_hash)
        code.consumed = True
        await code.save(using_db=connection)
    return JSONResponse({'access_token': access, 'token_type': 'Bearer', 'expires_in': 900,
                         'id_token': signed, 'scope': code.scope},
                        headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


@router.get('/oauth/userinfo')
@router.post('/oauth/userinfo')
async def userinfo(authorization: str = Header('')):
    if not authorization.startswith('Bearer '):
        return JSONResponse({'error': 'invalid_token'}, 401, headers={'WWW-Authenticate': 'Bearer'})
    record = await OIDCAccessToken.get_or_none(token_hash=digest(authorization[7:]))
    if not record or record.expires_at <= int(time.time()):
        return JSONResponse({'error': 'invalid_token'}, 401, headers={'WWW-Authenticate': 'Bearer'})
    client = await OIDCClient.get_or_none(client_id=record.client_id, enabled=True)
    claims = await profile(record.subject, record.scope)
    if not client or claims is None:
        return JSONResponse({'error': 'invalid_token'}, 401, headers={'WWW-Authenticate': 'Bearer'})
    return JSONResponse(claims, headers={'Cache-Control': 'no-store'})


@router.post('/oauth/revoke')
async def revoke(request: Request):
    try:
        form = await form_data(request)
    except (ValueError, UnicodeError):
        return oauth_error('invalid_request')
    async with in_transaction() as connection:
        client = await authenticated_client(request, form, connection)
        if not client:
            return oauth_error('invalid_client', 401)
        await OIDCAccessToken.filter(client_id=client.client_id, token_hash=digest(
            form.get('token', ''))).using_db(connection).delete()
    return JSONResponse({}, headers={'Cache-Control': 'no-store'})

"""OIDC integration tests using disposable local PostgreSQL databases only."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import parse_qs, quote, urlsplit
import uuid

import asyncpg
import httpx
import jwt
from tortoise import Tortoise

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from api.models.db_models import OIDCClient, OIDCCode, OIDCAccessToken, UserDBModel
from api.models.jwt_tool import create_jwt
from api.models.oidc import b64, digest, signing_key, valid_redirect
from scripts.create_oidc_key import create_key


class RedirectTests(unittest.TestCase):
    def test_callback_restrictions(self):
        for uri in ['https://example.org/cb?a=1', 'http://localhost:1234/cb', 'http://[::1]:2345/cb']:
            self.assertTrue(valid_redirect(uri), uri)
        for uri in ['http://example.org/cb', 'javascript:alert(1)', 'https://example.org/#fragment',
                    'https://u:p@example.org', 'https://*.example.org', 'https://example.org/\n']:
            self.assertFalse(valid_redirect(uri), uri)


class OIDCTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        password_file = ROOT / '.local/postgres-admin-password'
        if not password_file.exists():
            self.skipTest('Start the isolated local PostgreSQL cluster first.')
        asyncio.get_running_loop().slow_callback_duration = 2
        self.admin_db = await asyncpg.connect(host='127.0.0.1', port=55432, user='creator_admin',
                                              password=password_file.read_text().strip(), database='postgres')
        self.name = 'creatorsn_oidc_test_' + uuid.uuid4().hex
        await self.admin_db.execute(f'CREATE DATABASE "{self.name}" OWNER creatorsn')
        password = (ROOT / '.local/postgres-app-password').read_text().strip()
        self.url = f'postgres://creatorsn:{quote(password, safe="")}@127.0.0.1:55432/{self.name}'
        result = subprocess.run([sys.executable, str(ROOT/'backend/scripts/init_database.py')],
                                cwd=ROOT, env={**os.environ, 'DATABASE_URL': self.url},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        await Tortoise.init(db_url=self.url, modules={'models': ['api.models.db_models']})
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'.local')
        key_path = Path(self.temp.name) / 'key.pem'
        create_key(key_path)
        self.old_key = os.environ.get('OIDC_SIGNING_KEY_FILE')
        os.environ['OIDC_SIGNING_KEY_FILE'] = str(key_path)
        old_cwd = Path.cwd()
        try:
            os.chdir(ROOT/'backend')
            from api.controllers import oidc
            from app import app
        finally:
            os.chdir(old_cwd)
        self.module = oidc
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='https://creatorsn.com')
        self.headers = self.headers_for(oidc.config['root_name'], 'admin')
        await UserDBModel.create(userid='member', pwd='unused', role='user', name='Member', email='member@example.org')
        await UserDBModel.create(userid='manager', pwd='unused', role='admin')
        self.member_headers = self.headers_for('member', 'user')
        self.verifier = 'a' * 43

    def headers_for(self, userid, role):
        from api.models.database import CONFIG_PATH
        config = json.loads(CONFIG_PATH.read_text())
        token, _ = create_jwt({'userid': userid, 'role': role}, config['jwt_key'])
        return {'Api-key': token}

    async def asyncTearDown(self):
        await self.http.aclose()
        await Tortoise.close_connections()
        if self.old_key is None:
            os.environ.pop('OIDC_SIGNING_KEY_FILE', None)
        else:
            os.environ['OIDC_SIGNING_KEY_FILE'] = self.old_key
        signing_key.cache_clear()
        self.temp.cleanup()
        await self.admin_db.execute(f'DROP DATABASE "{self.name}" WITH (FORCE)')
        await self.admin_db.close()

    async def new_client(self, client_type='public'):
        response = await self.http.post('/oidc/clients', headers=self.headers, json={
            'name': 'Test application', 'redirect_uris': ['https://example.org/callback?fixed=1'],
            'client_type': client_type,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def authorization(self, client):
        return {'client_id': client['client_id'], 'redirect_uri': client['redirect_uris'][0],
                'response_type': 'code', 'scope': 'openid profile email', 'state': 'unchanged-state',
                'nonce': 'test-nonce', 'code_challenge_method': 'S256',
                'code_challenge': b64(hashlib.sha256(self.verifier.encode()).digest())}

    async def grant(self, client, headers=None):
        response = await self.http.post('/oidc/authorize', headers=headers or self.member_headers,
                                        json={**self.authorization(client), 'decision': 'allow'})
        self.assertEqual(response.status_code, 200, response.text)
        query = parse_qs(urlsplit(response.json()['redirect_to']).query)
        self.assertEqual(query['state'], ['unchanged-state'])
        self.assertEqual(query['fixed'], ['1'])
        return query['code'][0]

    def exchange(self, client, code):
        return {'grant_type': 'authorization_code', 'client_id': client['client_id'], 'code': code,
                'redirect_uri': client['redirect_uris'][0], 'code_verifier': self.verifier}

    async def test_admin_only_management_and_live_role_checks(self):
        client = await self.new_client()
        for headers, expected in [({}, 401), (self.member_headers, 403),
                                   (self.headers_for('member', 'admin'), 403)]:
            for method, path, body in [
                ('GET', '/oidc/clients', None), ('POST', '/oidc/clients', {}),
                ('PUT', '/oidc/clients/'+client['client_id'], {}),
                ('DELETE', '/oidc/clients/'+client['client_id'], None),
                ('POST', '/oidc/clients/'+client['client_id']+'/rotate-secret', None),
            ]:
                response = await self.http.request(method, path, headers=headers, json=body)
                self.assertEqual(response.status_code, expected, response.text)
        manager = self.headers_for('manager', 'admin')
        self.assertEqual((await self.http.get('/oidc/clients', headers=manager)).status_code, 200)
        await UserDBModel.filter(userid='manager').update(role='user')
        self.assertEqual((await self.http.get('/oidc/clients', headers=manager)).status_code, 403)
        await UserDBModel.filter(userid='manager').update(role='notadmin')
        self.assertEqual((await self.http.get('/oidc/clients', headers=manager)).status_code, 403)

    async def test_public_flow_signature_scopes_and_replay_revocation(self):
        client = await self.new_client()
        discovery = (await self.http.get('/.well-known/openid-configuration')).json()
        self.assertEqual(discovery['issuer'], 'https://creatorsn.com')
        public = (await self.http.get('/oauth/jwks')).json()['keys'][0]
        self.assertNotIn('d', public)
        code = await self.grant(client)
        response = await self.http.post('/oauth/token', data=self.exchange(client, code))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        result = response.json()
        claims = jwt.decode(result['id_token'], jwt.PyJWK.from_dict(public).key,
                            algorithms=['RS256'], audience=client['client_id'], issuer=discovery['issuer'])
        self.assertEqual(claims['nonce'], 'test-nonce')
        self.assertEqual(claims['sub'], 'member')
        self.assertFalse(claims['email_verified'])
        self.assertEqual(claims['at_hash'], b64(hashlib.sha256(result['access_token'].encode()).digest()[:16]))
        headers = {'Authorization': 'Bearer '+result['access_token']}
        self.assertEqual((await self.http.get('/oauth/userinfo', headers=headers)).json()['name'], 'Member')
        record = await OIDCAccessToken.get(token_hash=digest(result['access_token']))
        self.assertNotEqual(record.token_hash, result['access_token'])
        replay = await self.http.post('/oauth/token', data=self.exchange(client, code))
        self.assertEqual(replay.json()['error'], 'invalid_grant')
        self.assertEqual((await self.http.get('/oauth/userinfo', headers=headers)).status_code, 401)

    async def test_confidential_secret_shown_once_basic_auth_and_rotation(self):
        client = await self.new_client('confidential')
        self.assertTrue(client['client_secret'])
        listed = (await self.http.get('/oidc/clients', headers=self.headers)).json()[0]
        self.assertNotIn('client_secret', listed)
        self.assertNotIn('secret_hash', listed)
        stored = await OIDCClient.get(client_id=client['client_id'])
        self.assertNotEqual(stored.secret_hash, client['client_secret'])
        code = await self.grant(client)
        data = self.exchange(client, code)
        self.assertEqual((await self.http.post('/oauth/token', data=data)).status_code, 401)
        credentials = httpx.BasicAuth(client['client_id'], client['client_secret'])
        response = await self.http.post('/oauth/token', data=data, auth=credentials)
        self.assertEqual(response.status_code, 200, response.text)
        rotated = await self.http.post('/oidc/clients/'+client['client_id']+'/rotate-secret', headers=self.headers)
        self.assertNotEqual(rotated.json()['client_secret'], client['client_secret'])
        headers = {'Authorization': 'Bearer '+response.json()['access_token']}
        self.assertEqual((await self.http.get('/oauth/userinfo', headers=headers)).status_code, 401)
        code2 = await self.grant(client)
        self.assertEqual((await self.http.post('/oauth/token', data=self.exchange(client, code2), auth=credentials)).status_code, 401)
        self.assertEqual((await self.http.post('/oauth/token', data=self.exchange(client, code2),
            auth=httpx.BasicAuth(client['client_id'], rotated.json()['client_secret']))).status_code, 200)

    async def test_bad_redirect_pkce_scope_and_expiry(self):
        client = await self.new_client()
        original = self.authorization(client)
        for change in [{'redirect_uri': 'https://evil.example/callback'}, {'code_challenge_method': 'plain'},
                       {'scope': 'openid admin'}, {'response_type': 'token'}]:
            response = await self.http.get('/oauth/authorize', params={**original, **change})
            self.assertEqual(response.status_code, 400, response.text)
            self.assertNotIn('location', response.headers)
        response = await self.http.get('/oauth/authorize', params=original)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['location'].startswith('https://creatorsn.com/#/oauth/authorize?'))
        code = await self.grant(client)
        data = self.exchange(client, code)
        wrong = await self.http.post('/oauth/token', data={**data, 'code_verifier': 'b'*43})
        self.assertEqual(wrong.json()['error'], 'invalid_grant')
        wrong = await self.http.post('/oauth/token', data={**data, 'redirect_uri': 'https://evil.example'})
        self.assertEqual(wrong.json()['error'], 'invalid_grant')
        await OIDCCode.filter(code_hash=digest(code)).update(expires_at=int(time.time())-1)
        self.assertEqual((await self.http.post('/oauth/token', data=data)).json()['error'], 'invalid_grant')

    async def test_disable_delete_deny_and_explicit_consent(self):
        client = await self.new_client()
        auth = self.authorization(client)
        self.assertEqual((await self.http.post('/oidc/authorize', json=auth, headers=self.member_headers)).status_code, 400)
        deny = await self.http.post('/oidc/authorize', json={**auth, 'decision': 'deny'}, headers=self.member_headers)
        self.assertEqual(parse_qs(urlsplit(deny.json()['redirect_to']).query)['error'], ['access_denied'])
        code = await self.grant(client)
        body = {key: client[key] for key in ('name', 'description', 'client_type', 'redirect_uris')}
        response = await self.http.put('/oidc/clients/'+client['client_id'], headers=self.headers, json={**body, 'enabled': False})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.http.post('/oauth/token', data=self.exchange(client, code))).status_code, 401)
        response = await self.http.delete('/oidc/clients/'+client['client_id'], headers=self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(await OIDCCode.all().count(), 0)

    async def test_concurrent_code_consumption_and_revocation(self):
        client = await self.new_client()
        code = await self.grant(client)
        responses = await asyncio.gather(*(self.http.post('/oauth/token', data=self.exchange(client, code)) for _ in range(2)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 400])
        self.assertEqual(await OIDCAccessToken.all().count(), 0)  # replay revokes the winning token
        code = await self.grant(client)
        result = (await self.http.post('/oauth/token', data=self.exchange(client, code))).json()
        response = await self.http.post('/oauth/revoke', data={'client_id': client['client_id'], 'token': result['access_token']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((await self.http.get('/oauth/userinfo', headers={'Authorization': 'Bearer '+result['access_token']})).status_code, 401)

    async def test_no_role_escalation_via_registration_or_profile(self):
        payload = {'userid': 'newmember', 'pwd': 'test-password-only', 'role': 'admin',
                   'invite_code': self.module.config['invite_code']}
        response = await self.http.post('/apply_user', json=payload)
        self.assertEqual(response.json()['code'], 200, response.text)
        self.assertEqual((await UserDBModel.get(userid='newmember')).role, 'user')
        self.assertNotIn('pwd', response.json()['data'])
        response = await self.http.post('/update_me', headers=self.member_headers, json={'role': 'admin', 'name': 'Updated'})
        self.assertEqual(response.json()['code'], 200, response.text)
        self.assertEqual((await UserDBModel.get(userid='member')).role, 'user')

    async def test_nonce_optional_scopes_minimized_and_key_fail_closed(self):
        client = await self.new_client()
        request = {**self.authorization(client), 'scope': 'openid', 'nonce': None, 'decision': 'allow'}
        response = await self.http.post('/oidc/authorize', headers=self.member_headers, json=request)
        code = parse_qs(urlsplit(response.json()['redirect_to']).query)['code'][0]
        result = (await self.http.post('/oauth/token', data=self.exchange(client, code))).json()
        public = (await self.http.get('/oauth/jwks')).json()['keys'][0]
        claims = jwt.decode(result['id_token'], jwt.PyJWK.from_dict(public).key, algorithms=['RS256'], audience=client['client_id'])
        self.assertNotIn('email', claims)
        self.assertNotIn('name', claims)
        self.assertNotIn('nonce', claims)
        os.environ['OIDC_SIGNING_KEY_FILE'] = str(Path(self.temp.name)/'missing.pem')
        self.assertEqual((await self.http.get('/.well-known/openid-configuration')).status_code, 503)

    async def test_api_prefix_no_cache_cors_and_duplicate_parameters(self):
        client = await self.new_client()
        response = await self.http.get('/api/oidc/clients', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        response = await self.http.options('/oauth/token', headers={
            'Origin': 'https://client.example', 'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'authorization,content-type'})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['access-control-allow-origin'], '*')
        self.assertNotIn('access-control-allow-credentials', response.headers)
        response = await self.http.post('/oauth/token', content='grant_type=authorization_code&client_id=a&client_id=b',
                                       headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(response.json()['error'], 'invalid_request')
        response = await self.http.get('/oauth/authorize', params=[*self.authorization(client).items(), ('state', 'duplicate')])
        self.assertEqual(response.status_code, 400)
        response = await self.http.post('/oauth/token', content='x'*16385,
                                       headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(response.json()['error'], 'invalid_request')


if __name__ == '__main__':
    unittest.main()

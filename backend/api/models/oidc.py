"""OIDC primitives. Keys are operator-provisioned, never generated per request."""
import base64
import hashlib
import hmac
import json
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.models.database import CONFIG_PATH


def settings():
    with CONFIG_PATH.open() as stream:
        config = json.load(stream).get('oidc', {})
    issuer = os.environ.get('OIDC_ISSUER', config.get('issuer', 'https://creatorsn.com')).rstrip('/')
    if urlsplit(issuer).scheme != 'https' or urlsplit(issuer).query or urlsplit(issuer).fragment:
        raise ValueError('OIDC issuer must be a fixed HTTPS URL')
    key_path = os.environ.get('OIDC_SIGNING_KEY_FILE', config.get(
        'signing_key_file', str(CONFIG_PATH.parents[1] / 'db/oidc-signing.pem')))
    return issuer, key_path


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_secret(secret):
    salt = os.urandom(16)
    value = hashlib.scrypt(secret.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ':' + value.hex()


def check_secret(secret, encoded):
    if not encoded or len(secret) > 512:
        return False
    salt, expected = encoded.split(':')
    value = hashlib.scrypt(secret.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(value.hex(), expected)


@lru_cache(maxsize=4)
def signing_key(path):
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError('An RSA private key of at least 2048 bits is required')
    numbers = key.public_key().public_numbers()
    public = {'kty': 'RSA', 'e': b64(numbers.e.to_bytes((numbers.e.bit_length()+7)//8, 'big')),
              'n': b64(numbers.n.to_bytes((numbers.n.bit_length()+7)//8, 'big'))}
    kid = b64(hashlib.sha256(json.dumps(public, sort_keys=True, separators=(',', ':')).encode()).digest())
    return key, {**public, 'kid': kid, 'use': 'sig', 'alg': 'RS256'}


def get_signer():
    return signing_key(settings()[1])


def encode_id_token(claims):
    key, public = get_signer()
    return jwt.encode(claims, key, algorithm='RS256', headers={'kid': public['kid']})


def valid_redirect(value):
    """Exact registrations only; no fragments, credentials, wildcards or non-web schemes."""
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        return bool(
            len(value) <= 2048 and parsed.hostname and '#' not in value and '\\' not in value
            and not parsed.username and not parsed.password and '*' not in value
            and not any(char.isspace() or ord(char) < 32 for char in value)
            and (parsed.scheme == 'https' or
                 (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1')))
        )
    except ValueError:
        return False

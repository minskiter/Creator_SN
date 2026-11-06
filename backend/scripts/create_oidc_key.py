"""Provision a persistent RSA OIDC key. Never overwrite an existing signing key."""
import argparse
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def create_key(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(pem)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', required=True)
    create_key(parser.parse_args().path)
    print('OIDC signing key provisioned (keep it private and include it in encrypted backups).')

import sys
import os
# ensure project root is on sys.path
root = os.path.dirname(os.path.abspath(__file__))
# add ai-customer-backend package to path
backend_path = os.path.join(root, 'ai-customer-backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
# also allow root as fallback
if root not in sys.path:
    sys.path.insert(0, root)

import base64
from app.security import url_guard
from app.utils import crypto

print('Testing _is_allowlisted logic...')
url_guard.settings.CALLBACK_URL_ALLOWLIST = '*.trusted.com'
for host in ('sub.api.trusted.com', 'trusted.com', 'api.trusted.com', 'notrusted.com'):
    print(f"{host}: {url_guard._is_allowlisted(host)}")

print('\nTesting crypto key handling...')
try:
    from cryptography.fernet import Fernet
    # generate a real Fernet key
    fkey = Fernet.generate_key().decode('utf-8')
    print('Generated Fernet key length:', len(fkey))
    s = 'secret-value-123'
    enc = crypto.encrypt(s, secret_key=fkey)
    dec = crypto.decrypt(enc, secret_key=fkey)
    print('Fernet key roundtrip OK:', dec == s)

    # passphrase mode
    passphrase = 'my very secure passphrase'
    enc2 = crypto.encrypt(s, secret_key=passphrase)
    dec2 = crypto.decrypt(enc2, secret_key=passphrase)
    print('Passphrase roundtrip OK:', dec2 == s)
except Exception as e:
    print('Crypto tests skipped/unavailable:', e)

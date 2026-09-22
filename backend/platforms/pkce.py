"""PKCE, generated on the server.

The desktop app kept the verifier in a JavaScript closure. Here the browser
never sees it: it is stored encrypted against the OAuth session and used once,
when the code comes back.
"""

import base64
import hashlib
import secrets


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def generate_verifier() -> str:
    return _b64url(secrets.token_bytes(64))


def s256_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode()).digest())

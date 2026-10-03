import base64
import hashlib
import secrets


class Pkce:
    VERIFIER_BYTES = 64

    def __init__(self, verifier: str):
        self.verifier = verifier

    @classmethod
    def generate(cls) -> "Pkce":
        return cls(cls._b64url(secrets.token_bytes(cls.VERIFIER_BYTES)))

    def challenge(self) -> str:
        return self._b64url(self._digest())

    def hex_challenge(self) -> str:
        return self._digest().hex()

    def _digest(self) -> bytes:
        return hashlib.sha256(self.verifier.encode()).digest()

    @staticmethod
    def _b64url(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

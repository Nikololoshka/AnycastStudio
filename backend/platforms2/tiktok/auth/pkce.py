import base64
import hashlib
import secrets


class Pkce:
    VERIFIER_BYTES = 64

    def __init__(self, verifier: str):
        self.verifier = verifier

    @classmethod
    def generate(cls) -> "Pkce":
        return cls(base64.urlsafe_b64encode(secrets.token_bytes(cls.VERIFIER_BYTES)).decode().rstrip("="))

    def hex_challenge(self) -> str:
        return hashlib.sha256(self.verifier.encode()).hexdigest()

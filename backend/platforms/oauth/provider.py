from dataclasses import dataclass, field
from typing import Protocol

from .tokens import TokenBundle


@dataclass(frozen=True)
class Identity:
    external_id: str
    display_name: str
    avatar_url: str = ""
    extra: dict = field(default_factory=dict)


class PlatformProvider(Protocol):
    name: str
    scopes: tuple[str, ...]
    uses_pkce: bool

    @property
    def redirect_uri(self) -> str: ...

    def code_challenge(self, verifier: str) -> str: ...

    def authorize_url(self, state: str, code_challenge: str | None) -> str: ...

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle: ...

    def refresh(self, refresh_token: str) -> TokenBundle: ...

    def fetch_identity(self, access_token: str) -> Identity: ...

    def revoke(self, token: str) -> None: ...

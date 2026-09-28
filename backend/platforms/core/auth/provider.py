from abc import ABC, abstractmethod
from typing import Self, TypeVar
from urllib.parse import urlencode

from pydantic import BaseModel

from ..config import OAuthCredentials, PlatformConfig
from ..errors import PlatformError, ProviderError
from ..http import PlatformClient, ResponseParser
from .identity import Identity
from .pkce import Pkce
from .tokens import TokenAnswer, TokenBundle

OAUTH_ATTEMPTS = 3

M = TypeVar("M", bound=BaseModel)


class OAuth2Provider(ABC):
    name: str
    label: str
    scopes: tuple[str, ...]
    uses_pkce = True
    authorize_endpoint: str
    token_endpoint: str
    client_id_param = "client_id"
    scope_separator = " "

    def __init__(self, client: PlatformClient, credentials: OAuthCredentials, redirect_uri: str):
        self.client = client
        self.redirect_uri = redirect_uri
        self._credentials = credentials
        self._parser = ResponseParser(self.label)

    @classmethod
    @abstractmethod
    def create(cls, config: PlatformConfig) -> Self: ...

    @abstractmethod
    def fetch_identity(self, access_token: str) -> Identity: ...

    @abstractmethod
    def revoke(self, access_token: str, refresh_token: str) -> None: ...

    def client_id(self) -> str:
        return self._configured(self._credentials.client_id, self._credentials.client_id_name)

    def client_secret(self) -> str:
        return self._configured(self._credentials.client_secret, self._credentials.client_secret_name)

    @staticmethod
    def _configured(value: str, name: str) -> str:
        if not value:
            raise ProviderError(f"{name} is not configured")
        return value

    def _send(self, method: str, url: str, attempts: int = OAUTH_ATTEMPTS, **kwargs):
        try:
            return self.client.send(method, url, attempts=attempts, **kwargs)
        except PlatformError as failure:
            raise ProviderError(failure.message, transient=failure.retryable) from None

    def code_challenge(self, verifier: str) -> str:
        return Pkce(verifier).challenge()

    def authorize_params(self, state: str, code_challenge: str | None) -> dict:
        params = {
            self.client_id_param: self.client_id(),
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scope_separator.join(self.scopes),
            "state": state,
        }
        if self.uses_pkce:
            params.update(code_challenge=code_challenge, code_challenge_method="S256")
        return params

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        return f"{self.authorize_endpoint}?{urlencode(self.authorize_params(state, code_challenge))}"

    def token_request(self, grant: dict) -> dict:
        credentials = {self.client_id_param: self.client_id(), "client_secret": self.client_secret()}
        return {"data": {**credentials, **grant}}

    def _answer(self, method: str, url: str, model: type[M], *, refusal: str | None = None, **kwargs) -> M:
        response = self._send(method, url, **kwargs)
        try:
            return self._parser.parse(response, model, refusal=refusal)
        except PlatformError as failure:
            raise ProviderError(failure.message) from None

    def _post_token(self, grant: dict) -> TokenBundle:
        response = self._send("POST", self.token_endpoint, **self.token_request(grant))
        try:
            answer = self._parser.parse(response, TokenAnswer)
        except PlatformError as failure:
            raise ProviderError(failure.message) from None

        if not answer.access_token:
            reason = answer.refusal_reason or f"HTTP {response.status_code}"
            raise ProviderError(f"{self.label} refused the token request: {reason[:200]}")

        return TokenBundle(
            access_token=answer.access_token,
            refresh_token=answer.refresh_token,
            expires_in=answer.expires_in,
            scopes=answer.scopes(self.scope_separator) or self.scopes,
        )

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle:
        return self._post_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier or "",
                "redirect_uri": self.redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> TokenBundle:
        return self._post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})

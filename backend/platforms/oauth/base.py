from typing import TypeVar
from urllib.parse import urlencode

from django.conf import settings
from pydantic import BaseModel

from config.wiring import container

from ..core.errors import PlatformError, ProviderError
from ..core.http import PlatformClient, ResponseParser
from . import pkce
from .redirect import callback_url
from .tokens import TokenAnswer, TokenBundle

OAUTH_ATTEMPTS = 3

M = TypeVar("M", bound=BaseModel)


class OAuth2Provider:
    name: str
    label: str
    scopes: tuple[str, ...]
    uses_pkce = True
    authorize_endpoint: str
    token_endpoint: str
    client_id_setting: str
    client_secret_setting: str
    client_id_param = "client_id"
    scope_separator = " "

    @property
    def redirect_uri(self) -> str:
        return callback_url(self.name)

    @staticmethod
    def _setting(name: str) -> str:
        value = getattr(settings, name, "")
        if not value:
            raise ProviderError(f"{name} is not configured")
        return value

    def client_id(self) -> str:
        return self._setting(self.client_id_setting)

    def client_secret(self) -> str:
        return self._setting(self.client_secret_setting)

    def transport(self, method: str, url: str, **kwargs):
        return PlatformClient(container().config.http, label=self.label).send(method, url, **kwargs)

    def _send(self, method: str, url: str, attempts: int = OAUTH_ATTEMPTS, **kwargs):
        try:
            return self.transport(method, url, attempts=attempts, **kwargs)
        except PlatformError as failure:
            raise ProviderError(failure.message, transient=failure.retryable) from None

    def code_challenge(self, verifier: str) -> str:
        return pkce.s256_challenge(verifier)

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
            return ResponseParser(self.label).parse(response, model, refusal=refusal)
        except PlatformError as failure:
            raise ProviderError(failure.message) from None

    def _post_token(self, grant: dict) -> TokenBundle:
        response = self._send("POST", self.token_endpoint, **self.token_request(grant))
        try:
            answer = ResponseParser(self.label).parse(response, TokenAnswer)
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

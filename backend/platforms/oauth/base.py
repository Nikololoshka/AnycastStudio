from urllib.parse import urlencode

from django.conf import settings

from .. import http
from ..http import PlatformFailure, json_dict
from . import pkce
from .errors import ProviderError
from .redirect import callback_url
from .tokens import TokenBundle

OAUTH_ATTEMPTS = 3


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
        return http.send(method, url, label=self.label, **kwargs)

    def _send(self, method: str, url: str, attempts: int = OAUTH_ATTEMPTS, **kwargs):
        try:
            return self.transport(method, url, attempts=attempts, **kwargs)
        except PlatformFailure as failure:
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

    def _post_token(self, grant: dict) -> TokenBundle:
        response = self._send("POST", self.token_endpoint, **self.token_request(grant))
        body = json_dict(response)

        if not body.get("access_token"):
            reason = body.get("error_description") or body.get("error") or f"HTTP {response.status_code}"
            raise ProviderError(f"{self.label} refused the token request: {str(reason)[:200]}")

        listed = str(body.get("scope", "")).split(self.scope_separator)
        granted = tuple(scope.strip() for scope in listed if scope.strip())
        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            scopes=granted or self.scopes,
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

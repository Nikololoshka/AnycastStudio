from urllib.parse import urlencode

from django.conf import settings

from ..http import PlatformFailure, json_dict
from ..oauth import Identity, ProviderError, TokenBundle, callback_url, pkce
from .api import API_ROOT, bearer, data_of, send

AUTH_ENDPOINT = "https://x.com/i/oauth2/authorize"
TOKEN_ENDPOINT = f"{API_ROOT}/oauth2/token"
REVOKE_ENDPOINT = f"{API_ROOT}/oauth2/revoke"
USER_INFO_ENDPOINT = f"{API_ROOT}/users/me"

OAUTH_ATTEMPTS = 3


def _send(method: str, url: str, attempts: int = OAUTH_ATTEMPTS, **kwargs):
    try:
        return send(method, url, attempts=attempts, **kwargs)
    except PlatformFailure as failure:
        raise ProviderError(failure.message, transient=failure.retryable) from None


class XProvider:
    name = "x"
    label = "X"
    uses_pkce = True
    scopes = ("tweet.read", "tweet.write", "users.read", "media.write", "offline.access")

    @property
    def redirect_uri(self) -> str:
        return callback_url(self.name)

    @staticmethod
    def _client_id() -> str:
        if not settings.X_CLIENT_ID:
            raise ProviderError("X_CLIENT_ID is not configured")
        return settings.X_CLIENT_ID

    @staticmethod
    def _client_secret() -> str:
        if not settings.X_CLIENT_SECRET:
            raise ProviderError("X_CLIENT_SECRET is not configured")
        return settings.X_CLIENT_SECRET

    def _client_auth(self) -> tuple[str, str]:
        return self._client_id(), self._client_secret()

    def code_challenge(self, verifier: str) -> str:
        return pkce.s256_challenge(verifier)

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id(),
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    def _post_token(self, data: dict) -> TokenBundle:
        response = _send("POST", TOKEN_ENDPOINT, data={**data, "client_id": self._client_id()}, auth=self._client_auth())
        body = json_dict(response)

        if not body.get("access_token"):
            reason = body.get("error_description") or body.get("error") or f"HTTP {response.status_code}"
            raise ProviderError(f"X refused the token request: {str(reason)[:200]}")

        scopes = tuple(scope for scope in str(body.get("scope", "")).split() if scope)
        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            scopes=scopes or self.scopes,
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

    def fetch_identity(self, access_token: str) -> Identity:
        response = _send(
            "GET", USER_INFO_ENDPOINT, params={"user.fields": "profile_image_url"}, headers=bearer(access_token)
        )
        user = data_of(json_dict(response))
        if not user.get("id"):
            raise ProviderError("X did not say which account signed in")

        return Identity(
            external_id=str(user["id"]),
            display_name=str(user.get("username") or user.get("name") or ""),
            avatar_url=str(user.get("profile_image_url") or ""),
        )

    def _revoke_one(self, token: str, hint: str) -> None:
        _send(
            "POST",
            REVOKE_ENDPOINT,
            attempts=1,
            data={"token": token, "token_type_hint": hint, "client_id": self._client_id()},
            auth=self._client_auth(),
        )

    def revoke(self, access_token: str, refresh_token: str) -> None:
        refusals: list[ProviderError] = []
        for token, hint in ((refresh_token, "refresh_token"), (access_token, "access_token")):
            if not token:
                continue
            try:
                self._revoke_one(token, hint)
            except ProviderError as error:
                refusals.append(error)
        if refusals:
            raise refusals[0]

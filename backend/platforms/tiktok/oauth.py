from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from ..http import PlatformFailure, json_dict
from ..oauth import Identity, ProviderError, TokenBundle, pkce
from .api import API_ROOT, data_of, send

AUTH_ENDPOINT = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_ENDPOINT = f"{API_ROOT}/oauth/token/"
REVOKE_ENDPOINT = f"{API_ROOT}/oauth/revoke/"
USER_INFO_ENDPOINT = f"{API_ROOT}/user/info/"

OAUTH_ATTEMPTS = 3


def _send(method: str, url: str, attempts: int = OAUTH_ATTEMPTS, **kwargs):
    try:
        return send(method, url, attempts=attempts, **kwargs)
    except PlatformFailure as failure:
        raise ProviderError(failure.message, transient=failure.retryable) from None


class TikTokProvider:
    name = "tiktok"
    label = "TikTok"
    uses_pkce = True
    scopes = ("user.info.basic", "video.publish")

    @property
    def redirect_uri(self) -> str:
        return f"{settings.PUBLIC_ORIGIN}{reverse('social-callback', args=[self.name])}"

    @staticmethod
    def _client_key() -> str:
        if not settings.TIKTOK_CLIENT_KEY:
            raise ProviderError("TIKTOK_CLIENT_KEY is not configured")
        return settings.TIKTOK_CLIENT_KEY

    @staticmethod
    def _client_secret() -> str:
        if not settings.TIKTOK_CLIENT_SECRET:
            raise ProviderError("TIKTOK_CLIENT_SECRET is not configured")
        return settings.TIKTOK_CLIENT_SECRET

    def code_challenge(self, verifier: str) -> str:
        return pkce.hex_s256_challenge(verifier)

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "client_key": self._client_key(),
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": ",".join(self.scopes),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    def _post_token(self, data: dict) -> TokenBundle:
        response = _send("POST", TOKEN_ENDPOINT, data=data)
        body = json_dict(response)

        if not body.get("access_token"):
            reason = body.get("error_description") or body.get("error") or f"HTTP {response.status_code}"
            raise ProviderError(f"TikTok refused the token request: {str(reason)[:200]}")

        scopes = tuple(scope for scope in str(body.get("scope", "")).split(",") if scope)
        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            scopes=scopes or self.scopes,
        )

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle:
        return self._post_token(
            {
                "client_key": self._client_key(),
                "client_secret": self._client_secret(),
                "code": code,
                "code_verifier": code_verifier or "",
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            }
        )

    def refresh(self, refresh_token: str) -> TokenBundle:
        return self._post_token(
            {
                "client_key": self._client_key(),
                "client_secret": self._client_secret(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )

    def fetch_identity(self, access_token: str) -> Identity:
        response = _send(
            "GET",
            USER_INFO_ENDPOINT,
            params={"fields": "open_id,display_name,avatar_url"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            user = data_of(response).get("user") or {}
        except PlatformFailure as failure:
            raise ProviderError(failure.message) from None

        if not user.get("open_id"):
            raise ProviderError("TikTok did not say which account signed in")

        return Identity(
            external_id=str(user["open_id"]),
            display_name=user.get("display_name", ""),
            avatar_url=user.get("avatar_url", ""),
        )

    def revoke(self, access_token: str, refresh_token: str) -> None:
        _send(
            "POST",
            REVOKE_ENDPOINT,
            attempts=1,
            data={"client_key": self._client_key(), "client_secret": self._client_secret(), "token": access_token},
        )

from urllib.parse import urlencode

from django.conf import settings

from ..oauth import Identity, ProviderError, TokenBundle, callback_url, pkce
from ..http import PlatformFailure, json_dict, send

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"

LABEL = "Google"
OAUTH_ATTEMPTS = 3


def _send(method: str, url: str, attempts: int = OAUTH_ATTEMPTS, **kwargs):
    try:
        return send(method, url, label=LABEL, attempts=attempts, **kwargs)
    except PlatformFailure as failure:
        raise ProviderError(failure.message, transient=failure.retryable) from None


class YouTubeProvider:
    name = "youtube"
    label = "YouTube"
    uses_pkce = True
    scopes = (
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    )

    @property
    def redirect_uri(self) -> str:
        return callback_url(self.name)

    @staticmethod
    def _client_id() -> str:
        if not settings.YOUTUBE_CLIENT_ID:
            raise ProviderError("YOUTUBE_CLIENT_ID is not configured")
        return settings.YOUTUBE_CLIENT_ID

    @staticmethod
    def _client_secret() -> str:
        if not settings.YOUTUBE_CLIENT_SECRET:
            raise ProviderError("YOUTUBE_CLIENT_SECRET is not configured")
        return settings.YOUTUBE_CLIENT_SECRET

    def code_challenge(self, verifier: str) -> str:
        return pkce.s256_challenge(verifier)

    def authorize_url(self, state: str, code_challenge: str | None) -> str:
        params = {
            "client_id": self._client_id(),
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    def _post_token(self, data: dict) -> TokenBundle:
        response = _send("POST", TOKEN_ENDPOINT, data=data)
        body = json_dict(response)

        if not body.get("access_token"):
            raise ProviderError(f"Unexpected response from Google (HTTP {response.status_code})")

        return TokenBundle(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            scopes=tuple(str(body.get("scope", "")).split()) or self.scopes,
        )

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle:
        return self._post_token(
            {
                "client_id": self._client_id(),
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
                "client_id": self._client_id(),
                "client_secret": self._client_secret(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )

    def fetch_identity(self, access_token: str) -> Identity:
        response = _send(
            "GET",
            CHANNELS_ENDPOINT,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        items = json_dict(response).get("items") or []
        if not items:
            raise ProviderError("This Google account has no YouTube channel")

        channel = items[0]
        snippet = channel.get("snippet") or {}
        thumbnails = snippet.get("thumbnails") or {}

        return Identity(
            external_id=str(channel.get("id", "")),
            display_name=snippet.get("title", ""),
            avatar_url=(thumbnails.get("default") or {}).get("url", ""),
            extra={"customUrl": snippet.get("customUrl", "")},
        )

    def revoke(self, access_token: str, refresh_token: str) -> None:
        _send("POST", REVOKE_ENDPOINT, attempts=1, data={"token": refresh_token or access_token})

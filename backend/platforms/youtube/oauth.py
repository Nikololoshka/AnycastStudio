from .. import http
from ..http import json_dict
from ..oauth import Identity, OAuth2Provider, ProviderError

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"

LABEL = "Google"


class YouTubeProvider(OAuth2Provider):
    name = "youtube"
    label = "YouTube"
    scopes = (
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    )
    authorize_endpoint = AUTH_ENDPOINT
    token_endpoint = TOKEN_ENDPOINT
    client_id_setting = "YOUTUBE_CLIENT_ID"
    client_secret_setting = "YOUTUBE_CLIENT_SECRET"

    def transport(self, method: str, url: str, **kwargs):
        return http.send(method, url, label=LABEL, **kwargs)

    def authorize_params(self, state: str, code_challenge: str | None) -> dict:
        return {
            **super().authorize_params(state, code_challenge),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }

    def fetch_identity(self, access_token: str) -> Identity:
        response = self._send(
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
        self._send("POST", REVOKE_ENDPOINT, attempts=1, data={"token": refresh_token or access_token})

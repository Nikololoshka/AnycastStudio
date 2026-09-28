from config.wiring import container

from ..core.http import PlatformClient
from ..oauth import Identity, OAuth2Provider, ProviderError
from .responses import ChannelList

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
        return PlatformClient(container().config.http, label=LABEL).send(method, url, **kwargs)

    def authorize_params(self, state: str, code_challenge: str | None) -> dict:
        return {
            **super().authorize_params(state, code_challenge),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }

    def fetch_identity(self, access_token: str) -> Identity:
        channels = self._answer(
            "GET",
            CHANNELS_ENDPOINT,
            ChannelList,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if not channels.items:
            raise ProviderError("This Google account has no YouTube channel")

        channel = channels.items[0]
        return Identity(
            external_id=channel.id,
            display_name=channel.snippet.title,
            avatar_url=channel.snippet.thumbnails.default.url,
            extra={"customUrl": channel.snippet.custom_url},
        )

    def revoke(self, access_token: str, refresh_token: str) -> None:
        self._send("POST", REVOKE_ENDPOINT, attempts=1, data={"token": refresh_token or access_token})

from typing import Self

from ..core.auth import Identity, OAuth2Provider, Pkce
from ..core.config import PlatformConfig
from ..core.errors import PlatformError, ProviderError
from .client import API_ROOT, TikTokClient
from .responses import UserData

AUTH_ENDPOINT = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_ENDPOINT = f"{API_ROOT}/oauth/token/"
REVOKE_ENDPOINT = f"{API_ROOT}/oauth/revoke/"
USER_INFO_ENDPOINT = f"{API_ROOT}/user/info/"


class TikTokProvider(OAuth2Provider):
    name = "tiktok"
    label = "TikTok"
    scopes = ("user.info.basic", "video.publish")
    authorize_endpoint = AUTH_ENDPOINT
    token_endpoint = TOKEN_ENDPOINT
    client_id_param = "client_key"
    scope_separator = ","

    @classmethod
    def create(cls, config: PlatformConfig) -> Self:
        return cls(TikTokClient(config.http), config.credentials_of(cls.name), config.callback_url(cls.name))

    def code_challenge(self, verifier: str) -> str:
        return Pkce(verifier).hex_challenge()

    def fetch_identity(self, access_token: str) -> Identity:
        response = self._send(
            "GET",
            USER_INFO_ENDPOINT,
            params={"fields": "open_id,display_name,avatar_url"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            user = self.client.data_of(response, UserData, refusal="TikTok did not say which account signed in").user
        except PlatformError as failure:
            raise ProviderError(failure.message) from None

        return Identity(external_id=user.open_id, display_name=user.display_name, avatar_url=user.avatar_url)

    def revoke(self, access_token: str, refresh_token: str) -> None:
        self._send(
            "POST",
            REVOKE_ENDPOINT,
            attempts=1,
            data={"client_key": self.client_id(), "client_secret": self.client_secret(), "token": access_token},
        )

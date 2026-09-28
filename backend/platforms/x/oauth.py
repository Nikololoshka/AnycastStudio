from typing import Self

from ..core.auth import Identity, OAuth2Provider
from ..core.config import PlatformConfig
from ..core.errors import ProviderError
from .client import API_ROOT, XClient
from .responses import Data, User

AUTH_ENDPOINT = "https://x.com/i/oauth2/authorize"
TOKEN_ENDPOINT = f"{API_ROOT}/oauth2/token"
REVOKE_ENDPOINT = f"{API_ROOT}/oauth2/revoke"
USER_INFO_ENDPOINT = f"{API_ROOT}/users/me"


class XProvider(OAuth2Provider):
    name = "x"
    label = "X"
    scopes = ("tweet.read", "tweet.write", "users.read", "media.write", "offline.access")
    authorize_endpoint = AUTH_ENDPOINT
    token_endpoint = TOKEN_ENDPOINT

    @classmethod
    def create(cls, config: PlatformConfig) -> Self:
        return cls(XClient(config.http), config.credentials_of(cls.name), config.callback_url(cls.name))

    def _client_auth(self) -> tuple[str, str]:
        return self.client_id(), self.client_secret()

    def token_request(self, grant: dict) -> dict:
        return {"data": {**grant, "client_id": self.client_id()}, "auth": self._client_auth()}

    def fetch_identity(self, access_token: str) -> Identity:
        user = self._answer(
            "GET",
            USER_INFO_ENDPOINT,
            Data[User],
            refusal="X did not say which account signed in",
            params={"user.fields": "profile_image_url"},
            headers=XClient.bearer(access_token),
        ).data

        return Identity(
            external_id=user.id,
            display_name=user.username or user.name,
            avatar_url=user.profile_image_url,
        )

    def _revoke_one(self, token: str, hint: str) -> None:
        self._send(
            "POST",
            REVOKE_ENDPOINT,
            attempts=1,
            data={"token": token, "token_type_hint": hint, "client_id": self.client_id()},
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

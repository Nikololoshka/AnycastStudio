from ..http import PlatformFailure
from ..oauth import Identity, OAuth2Provider, ProviderError, pkce
from .api import API_ROOT, data_of, send

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
    client_id_setting = "TIKTOK_CLIENT_KEY"
    client_secret_setting = "TIKTOK_CLIENT_SECRET"
    client_id_param = "client_key"
    scope_separator = ","

    def transport(self, method: str, url: str, **kwargs):
        return send(method, url, **kwargs)

    def code_challenge(self, verifier: str) -> str:
        return pkce.hex_s256_challenge(verifier)

    def fetch_identity(self, access_token: str) -> Identity:
        response = self._send(
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
        self._send(
            "POST",
            REVOKE_ENDPOINT,
            attempts=1,
            data={"client_key": self.client_id(), "client_secret": self.client_secret(), "token": access_token},
        )

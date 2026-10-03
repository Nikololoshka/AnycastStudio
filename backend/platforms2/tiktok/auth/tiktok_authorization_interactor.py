from typing import override
from urllib.parse import urlencode

from platforms2.core import AuthorizationError, AuthorizationInteractor, AuthProfile, AuthRequest, AuthToken

from ..tiktok_config import TikTokConfig
from ..tiktok_endpoints import TikTokEndpoints
from ..tiktok_http import TikTokHttp
from .pkce import Pkce
from .token_answer import TokenAnswer
from .user_info import UserInfo


class TikTokAuthorizationInteractor(AuthorizationInteractor):

    def __init__(self, config: TikTokConfig, http: TikTokHttp):
        self._config = config
        self._http = http

    @override
    def create_auth_request(self, state: str) -> AuthRequest:
        pkce = Pkce.generate()
        params = {
            "client_key": self._config.client_key,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": ",".join(self._config.scopes),
            "state": state,
            "code_challenge": pkce.hex_challenge(),
            "code_challenge_method": "S256",
        }
        return AuthRequest(
            url=f"{TikTokEndpoints.AUTHORIZE}?{urlencode(params)}",
            state=state,
            code_verifier=pkce.verifier,
        )

    @override
    async def create_auth_token(self, code: str, code_verifier: str) -> AuthToken:
        return await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": self._config.redirect_uri,
            }
        )

    @override
    async def refresh_auth_token(self, refresh_token: str) -> AuthToken:
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    @override
    async def fetch_auth_profile(self, access_token: str) -> AuthProfile:
        info = await self._http.answer(
            method="GET",
            url=TikTokEndpoints.USER_INFO,
            model=UserInfo,
            params={"fields": "open_id,display_name,avatar_url"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user = info.data.user
        return AuthProfile(external_id=user.open_id, display_name=user.display_name, avatar_url=user.avatar_url)

    @override
    async def revoke_auth_token(self, token: AuthToken) -> None:
        response = await self._http.request(
            "POST", TikTokEndpoints.REVOKE, data={**self._client(), "token": token.access_token}
        )
        if response.ok:
            return
        raise AuthorizationError(response.failure(), f"TikTok refused the revocation: {response.refusal()}")

    async def _token(self, grant_params: dict) -> AuthToken:
        answer = await self._http.answer(
            method="POST",
            url=TikTokEndpoints.TOKEN,
            model=TokenAnswer,
            data={**self._client(), **grant_params},
        )
        return answer.auth_token(self._config.scopes)

    def _client(self) -> dict:
        return {"client_key": self._config.client_key, "client_secret": self._config.client_secret}

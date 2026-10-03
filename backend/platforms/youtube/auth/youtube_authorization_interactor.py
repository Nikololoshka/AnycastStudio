from typing import override
from urllib.parse import urlencode

from platforms.core import (
    AuthorizationInteractor,
    AuthProfile,
    AuthRequest,
    AuthToken,
    Pkce,
    PlatformError,
    PlatformFailure,
)

from ..core import GoogleEndpoints, GoogleHttp, YouTubeConfig
from .answers import ChannelList, TokenAnswer


class YouTubeAuthorizationInteractor(AuthorizationInteractor):

    def __init__(self, config: YouTubeConfig, http: GoogleHttp):
        self._config = config
        self._http = http

    @override
    def create_auth_request(self, state: str) -> AuthRequest:
        pkce = Pkce.generate()
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self._config.scopes),
            "state": state,
            "code_challenge": pkce.challenge(),
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return AuthRequest(
            url=f"{GoogleEndpoints.AUTHORIZE}?{urlencode(params)}",
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
        channels = await self._http.answer(
            method="GET",
            url=GoogleEndpoints.CHANNELS,
            model=ChannelList,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if not channels.items:
            raise PlatformError(PlatformFailure.REFUSED, "This Google account has no YouTube channel")

        channel = channels.items[0]
        return AuthProfile(
            external_id=channel.id,
            display_name=channel.snippet.title,
            avatar_url=channel.snippet.thumbnails.default.url,
        )

    @override
    async def revoke_auth_token(self, token: AuthToken) -> None:
        revocable = token.refresh_token or token.access_token
        response = await self._http.request("POST", GoogleEndpoints.REVOKE, data={"token": revocable})
        if response.ok or response.body.get("error") == "invalid_token":
            return
        raise PlatformError(response.failure(), f"YouTube refused the revocation: {response.refusal()}")

    async def _token(self, grant_params: dict) -> AuthToken:
        form = {"client_id": self._config.client_id, "client_secret": self._config.client_secret, **grant_params}
        answer = await self._http.answer("POST", GoogleEndpoints.TOKEN, TokenAnswer, data=form)
        return answer.auth_token(self._config.scopes)

from typing import override
from urllib.parse import urlencode

import aiohttp

from platforms2.core import AuthorizationInteractor, AuthProfile, AuthRequest, AuthToken, Pkce, PlatformError

from ..core import XConfig, XEndpoints, XHttp
from .answers import Me, TokenAnswer


class XAuthorizationInteractor(AuthorizationInteractor):

    def __init__(self, config: XConfig, http: XHttp):
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
        }
        return AuthRequest(
            url=f"{XEndpoints.AUTHORIZE}?{urlencode(params)}",
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
        me = await self._http.answer(
            method="GET",
            url=XEndpoints.ME,
            model=Me,
            params={"user.fields": "profile_image_url"},
            headers=self._http.bearer(access_token),
        )
        user = me.data
        return AuthProfile(
            external_id=user.id,
            display_name=user.username or user.name,
            avatar_url=user.profile_image_url,
        )

    @override
    async def revoke_auth_token(self, token: AuthToken) -> None:
        refusals: list[PlatformError] = []
        for value, hint in ((token.refresh_token, "refresh_token"), (token.access_token, "access_token")):
            if not value:
                continue
            try:
                await self._revoke_one(value, hint)
            except PlatformError as error:
                refusals.append(error)
        if refusals:
            raise refusals[0]

    async def _revoke_one(self, value: str, hint: str) -> None:
        response = await self._http.request(
            "POST",
            XEndpoints.REVOKE,
            data={"token": value, "token_type_hint": hint, "client_id": self._config.client_id},
            auth=self._client_auth(),
        )
        if not response.ok:
            raise PlatformError(response.failure(), f"X refused the revocation: {response.refusal()}")

    async def _token(self, grant_params: dict) -> AuthToken:
        answer = await self._http.answer(
            method="POST",
            url=XEndpoints.TOKEN,
            model=TokenAnswer,
            data={**grant_params, "client_id": self._config.client_id},
            auth=self._client_auth(),
        )
        return answer.auth_token(self._config.scopes)

    def _client_auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self._config.client_id, self._config.client_secret)

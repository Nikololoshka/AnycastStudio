import logging
from typing import override
from urllib.parse import urlencode

from platforms.core import AuthorizationInteractor, AuthProfile, AuthRequest, AuthToken, PlatformError, PlatformFailure

from ..core import InstagramConfig, InstagramEndpoints, InstagramHttp
from .answers import DebugToken, Page, PageList, UserToken

logger = logging.getLogger(__name__)


class InstagramAuthorizationInteractor(AuthorizationInteractor):
    PAGE_FIELDS = "id,access_token,instagram_business_account"
    PROFILE_FIELDS = "id,instagram_business_account{id,username,name,profile_picture_url}"

    def __init__(self, config: InstagramConfig, http: InstagramHttp):
        self._config = config
        self._http = http

    @override
    def create_auth_request(self, state: str) -> AuthRequest:
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": ",".join(self._config.scopes),
            "state": state,
        }
        return AuthRequest(url=f"{InstagramEndpoints.AUTHORIZE}?{urlencode(params)}", state=state, code_verifier="")

    @override
    async def create_auth_token(self, code: str, code_verifier: str) -> AuthToken:
        short_lived = await self._user_token({"redirect_uri": self._config.redirect_uri, "code": code})
        long_lived = await self._user_token({"grant_type": "fb_exchange_token", "fb_exchange_token": short_lived})

        page = await self._linked_page(long_lived)
        if page is None:
            raise PlatformError(
                PlatformFailure.REFUSED,
                "No Instagram professional account is linked to a Facebook Page that was shared",
            )
        return AuthToken(access_token=page.access_token, scopes=self._config.scopes)

    @override
    async def refresh_auth_token(self, refresh_token: str) -> AuthToken:
        raise PlatformError(
            PlatformFailure.GRANT_REVOKED, "An Instagram connection cannot be refreshed; reconnect the account"
        )

    @override
    async def fetch_auth_profile(self, access_token: str) -> AuthProfile:
        page = await self._http.answer(
            method="GET",
            url=InstagramEndpoints.ME,
            model=Page,
            params={"fields": self.PROFILE_FIELDS},
            headers=self._http.authorization(access_token),
        )
        account = page.instagram_business_account
        if account is None or not account.id:
            raise PlatformError(PlatformFailure.REFUSED, "The Facebook Page has no Instagram professional account")

        return AuthProfile(
            external_id=account.id,
            display_name=account.username or account.name,
            avatar_url=account.profile_picture_url,
        )

    @override
    async def revoke_auth_token(self, token: AuthToken) -> None:
        owner = await self._debug_token(token.access_token)
        if not owner.data.user_id:
            raise PlatformError(PlatformFailure.UNEXPECTED, "Facebook did not say whose token this is")

        response = await self._http.request(
            "DELETE", InstagramEndpoints.permissions(owner.data.user_id), headers=self._app_authorization()
        )
        if not response.ok:
            raise PlatformError(response.failure(), f"Instagram refused the revocation: {response.refusal()}")

    async def _user_token(self, grant_params: dict) -> str:
        client = {"client_id": self._config.client_id, "client_secret": self._config.client_secret}
        answer = await self._http.answer(
            method="GET",
            url=InstagramEndpoints.TOKEN,
            model=UserToken,
            params={**client, **grant_params},
        )
        return answer.access_token

    async def _linked_page(self, user_token: str) -> Page | None:
        user = self._http.authorization(user_token)
        pages = await self._http.answer(
            method="GET",
            url=InstagramEndpoints.MY_PAGES,
            model=PageList,
            params={"fields": self.PAGE_FIELDS},
            headers=user,
        )
        if pages.data:
            return pages.linked()

        granted = await self._debug_token(user_token)
        for asset_id in granted.granted_asset_ids():
            page = await self._page_by_id(asset_id, user)
            if page is not None and page.is_linked:
                return page
        return None

    async def _page_by_id(self, asset_id: str, user: dict) -> Page | None:
        try:
            return await self._http.answer(
                method="GET",
                url=InstagramEndpoints.node(asset_id),
                model=Page,
                params={"fields": self.PAGE_FIELDS},
                headers=user,
            )
        except PlatformError as error:
            if error.transient:
                raise
            logger.info("Facebook asset %s granted to the app is not a Page: %s", asset_id, error.message)
            return None

    async def _debug_token(self, input_token: str) -> DebugToken:
        return await self._http.answer(
            method="GET",
            url=InstagramEndpoints.DEBUG_TOKEN,
            model=DebugToken,
            params={"input_token": input_token},
            headers=self._app_authorization(),
        )

    def _app_authorization(self) -> dict:
        return self._http.authorization(f"{self._config.client_id}|{self._config.client_secret}")

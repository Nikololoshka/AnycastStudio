import logging
from typing import Self

from ...core.auth import Identity, OAuth2Provider, TokenBundle
from ...core.config import PlatformConfig
from ...core.errors import ProviderError
from ..client import GRAPH_ROOT, GRAPH_VERSION, InstagramClient
from .responses import DebugToken, Page, PageList, UserToken

AUTH_ENDPOINT = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
TOKEN_ENDPOINT = f"{GRAPH_ROOT}/oauth/access_token"
DEBUG_TOKEN_ENDPOINT = f"{GRAPH_ROOT}/debug_token"

PAGE_FIELDS = "id,access_token,instagram_business_account"
IDENTITY_FIELDS = "id,instagram_business_account{id,username,name,profile_picture_url}"

logger = logging.getLogger(__name__)


def _linked_page(pages: list[Page]) -> Page | None:
    return next((page for page in pages if page.is_linked), None)


class InstagramProvider(OAuth2Provider):
    name = "instagram"
    label = "Instagram"
    uses_pkce = False
    scopes = ("instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement")
    authorize_endpoint = AUTH_ENDPOINT
    token_endpoint = TOKEN_ENDPOINT
    scope_separator = ","

    @classmethod
    def create(cls, config: PlatformConfig) -> Self:
        client = InstagramClient(config.http)
        return cls(client, config.credentials_of(cls.name), config.callback_url(cls.name))

    def _app_authorization(self) -> dict:
        return InstagramClient.authorization(f"{self.client_id()}|{self.client_secret()}")

    def code_challenge(self, verifier: str) -> str:
        raise ProviderError("Facebook Login is used without PKCE")

    def _user_token(self, grant: dict) -> str:
        credentials = {"client_id": self.client_id(), "client_secret": self.client_secret()}
        answer = self._answer(
            "GET", TOKEN_ENDPOINT, UserToken, refusal="Facebook did not issue a token", params={**credentials, **grant}
        )
        return answer.access_token

    def _granted_asset_ids(self, user_token: str) -> list[str]:
        token = self._answer(
            "GET",
            DEBUG_TOKEN_ENDPOINT,
            DebugToken,
            params={"input_token": user_token},
            headers=self._app_authorization(),
        )
        asset_ids: list[str] = []
        for grant in token.data.granular_scopes:
            for target in grant.target_ids:
                if target not in asset_ids:
                    asset_ids.append(target)
        return asset_ids

    def _page_by_id(self, asset_id: str, user: dict) -> Page | None:
        try:
            return self._answer("GET", f"{GRAPH_ROOT}/{asset_id}", Page, params={"fields": PAGE_FIELDS}, headers=user)
        except ProviderError as error:
            if error.transient:
                raise
            logger.info("Facebook asset %s granted to the app is not a Page: %s", asset_id, error.message)
            return None

    def _pages(self, user_token: str) -> list[Page]:
        user = InstagramClient.authorization(user_token)
        pages = self._answer(
            "GET", f"{GRAPH_ROOT}/me/accounts", PageList, params={"fields": PAGE_FIELDS}, headers=user
        ).data
        if pages:
            return pages
        granted = (self._page_by_id(asset_id, user) for asset_id in self._granted_asset_ids(user_token))
        return [page for page in granted if page is not None]

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle:
        short_lived = self._user_token({"redirect_uri": self.redirect_uri, "code": code})
        long_lived = self._user_token({"grant_type": "fb_exchange_token", "fb_exchange_token": short_lived})

        page = _linked_page(self._pages(long_lived))
        if page is None:
            raise ProviderError("No Instagram professional account is linked to a Facebook Page that was shared")

        return TokenBundle(access_token=page.access_token, scopes=self.scopes)

    def refresh(self, refresh_token: str) -> TokenBundle:
        raise ProviderError("An Instagram connection cannot be refreshed; reconnect the account")

    def fetch_identity(self, access_token: str) -> Identity:
        headers = InstagramClient.authorization(access_token)
        page = self._answer("GET", f"{GRAPH_ROOT}/me", Page, params={"fields": IDENTITY_FIELDS}, headers=headers)
        account = page.instagram_business_account
        if account is None or not account.id:
            raise ProviderError("The Facebook Page has no Instagram professional account")

        return Identity(
            external_id=account.id,
            display_name=account.username or account.name,
            avatar_url=account.profile_picture_url,
            extra={"page_id": page.id},
        )

    def revoke(self, access_token: str, refresh_token: str) -> None:
        app = self._app_authorization()
        token = self._answer(
            "GET", DEBUG_TOKEN_ENDPOINT, DebugToken, attempts=1, params={"input_token": access_token}, headers=app
        )
        if not token.data.user_id:
            raise ProviderError("Facebook did not say whose token this is")
        self._send("DELETE", f"{GRAPH_ROOT}/{token.data.user_id}/permissions", attempts=1, headers=app)

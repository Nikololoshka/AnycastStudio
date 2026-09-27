import logging
from ..http import json_dict
from ..oauth import Identity, OAuth2Provider, ProviderError, TokenBundle
from .api import GRAPH_ROOT, GRAPH_VERSION, authorization, send

AUTH_ENDPOINT = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
TOKEN_ENDPOINT = f"{GRAPH_ROOT}/oauth/access_token"
DEBUG_TOKEN_ENDPOINT = f"{GRAPH_ROOT}/debug_token"

PAGE_FIELDS = "id,access_token,instagram_business_account"
IDENTITY_FIELDS = "id,instagram_business_account{id,username,name,profile_picture_url}"

logger = logging.getLogger(__name__)


def _data_of(body: dict) -> dict:
    data = body.get("data")
    return data if isinstance(data, dict) else {}


def _pages_of(body: dict) -> list[dict]:
    pages = body.get("data")
    return [page for page in pages if isinstance(page, dict)] if isinstance(pages, list) else []


def _linked_page(pages: list[dict]) -> dict | None:
    for page in pages:
        if page.get("access_token") and isinstance(page.get("instagram_business_account"), dict):
            return page
    return None


class InstagramProvider(OAuth2Provider):
    name = "instagram"
    label = "Instagram"
    uses_pkce = False
    scopes = ("instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement")
    authorize_endpoint = AUTH_ENDPOINT
    token_endpoint = TOKEN_ENDPOINT
    client_id_setting = "INSTAGRAM_CLIENT_ID"
    client_secret_setting = "INSTAGRAM_CLIENT_SECRET"
    scope_separator = ","

    def transport(self, method: str, url: str, **kwargs):
        return send(method, url, **kwargs)

    def _json(self, method: str, url: str, **kwargs) -> dict:
        return json_dict(self._send(method, url, **kwargs))

    def _app_authorization(self) -> dict:
        return authorization(f"{self.client_id()}|{self.client_secret()}")

    def code_challenge(self, verifier: str) -> str:
        raise ProviderError("Facebook Login is used without PKCE")

    def _user_token(self, grant: dict) -> str:
        credentials = {"client_id": self.client_id(), "client_secret": self.client_secret()}
        body = self._json("GET", TOKEN_ENDPOINT, params={**credentials, **grant})
        if not body.get("access_token"):
            raise ProviderError("Facebook did not issue a token")
        return str(body["access_token"])

    def _granted_asset_ids(self, user_token: str) -> list[str]:
        body = self._json(
            "GET", DEBUG_TOKEN_ENDPOINT, params={"input_token": user_token}, headers=self._app_authorization()
        )
        asset_ids: list[str] = []
        for grant in _data_of(body).get("granular_scopes") or []:
            if not isinstance(grant, dict):
                continue
            for target in grant.get("target_ids") or []:
                if str(target) not in asset_ids:
                    asset_ids.append(str(target))
        return asset_ids

    def _page_by_id(self, asset_id: str, user: dict) -> dict | None:
        try:
            return self._json("GET", f"{GRAPH_ROOT}/{asset_id}", params={"fields": PAGE_FIELDS}, headers=user)
        except ProviderError as error:
            if error.transient:
                raise
            logger.info("Facebook asset %s granted to the app is not a Page: %s", asset_id, error.message)
            return None

    def _pages(self, user_token: str) -> list[dict]:
        user = authorization(user_token)
        pages = _pages_of(self._json("GET", f"{GRAPH_ROOT}/me/accounts", params={"fields": PAGE_FIELDS}, headers=user))
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

        return TokenBundle(access_token=str(page["access_token"]), scopes=self.scopes)

    def refresh(self, refresh_token: str) -> TokenBundle:
        raise ProviderError("An Instagram connection cannot be refreshed; reconnect the account")

    def fetch_identity(self, access_token: str) -> Identity:
        page = self._json(
            "GET", f"{GRAPH_ROOT}/me", params={"fields": IDENTITY_FIELDS}, headers=authorization(access_token)
        )
        account = page.get("instagram_business_account")
        if not isinstance(account, dict) or not account.get("id"):
            raise ProviderError("The Facebook Page has no Instagram professional account")

        return Identity(
            external_id=str(account["id"]),
            display_name=str(account.get("username") or account.get("name") or ""),
            avatar_url=str(account.get("profile_picture_url") or ""),
            extra={"page_id": str(page.get("id") or "")},
        )

    def revoke(self, access_token: str, refresh_token: str) -> None:
        app = self._app_authorization()
        body = self._json("GET", DEBUG_TOKEN_ENDPOINT, attempts=1, params={"input_token": access_token}, headers=app)
        user_id = _data_of(body).get("user_id")
        if not user_id:
            raise ProviderError("Facebook did not say whose token this is")
        self._json("DELETE", f"{GRAPH_ROOT}/{user_id}/permissions", attempts=1, headers=app)

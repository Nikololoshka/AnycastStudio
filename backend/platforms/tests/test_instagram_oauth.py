from urllib.parse import parse_qs, urlparse

from django.test import override_settings

from config.wiring import container
from platforms.core.errors import ProviderError
from platforms.instagram import InstagramProvider
from platforms.instagram.client import GRAPH_ROOT

from .base import FakeResponse, PlatformTestCase

USER_TOKEN = "EAAG.short-user-token"
LONG_USER_TOKEN = "EAAG.long-user-token"
PAGE_TOKEN = "EAAG.page-token"
PAGE = {"id": "1000", "access_token": PAGE_TOKEN, "instagram_business_account": {"id": "17841400000000001"}}
PAGE_WITHOUT_INSTAGRAM = {"id": "999", "access_token": "EAAG.other-page"}


class FacebookDouble:
    def __init__(self, pages=None, granted_pages=None, granted_instagram=None, page_by_id=None):
        self.pages = pages if pages is not None else [PAGE]
        self.granted_pages = granted_pages or []
        self.granted_instagram = granted_instagram or []
        self.page_by_id = page_by_id or {}
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        params = kwargs.get("params") or {}
        if url == f"{GRAPH_ROOT}/oauth/access_token":
            return FakeResponse(200, {"access_token": LONG_USER_TOKEN if "fb_exchange_token" in params else USER_TOKEN})
        if url == f"{GRAPH_ROOT}/me/accounts":
            return FakeResponse(200, {"data": self.pages})
        if url == f"{GRAPH_ROOT}/debug_token":
            scopes = [
                {"scope": "instagram_basic", "target_ids": self.granted_instagram},
                {"scope": "pages_show_list", "target_ids": self.granted_pages},
            ]
            return FakeResponse(200, {"data": {"user_id": "555", "granular_scopes": scopes}})
        if url.startswith(f"{GRAPH_ROOT}/") and url.rsplit("/", 1)[1] in self.page_by_id:
            return FakeResponse(200, self.page_by_id[url.rsplit("/", 1)[1]])
        if url.rsplit("/", 1)[1] in self.granted_instagram:
            return FakeResponse(
                400, {"error": {"message": "(#100) Tried accessing nonexisting field (access_token)", "code": 100}}
            )
        if url == f"{GRAPH_ROOT}/555/permissions":
            return FakeResponse(200, {"success": True})
        raise AssertionError(f"unexpected call to {method} {url}")


@override_settings(PUBLIC_REDIRECT_ORIGIN="http://localhost:5173")
class InstagramOAuthScenarios(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.provider = InstagramProvider.create(container().config)

    def test_the_consent_url_asks_facebook_for_the_publishing_scopes(self):
        url = self.provider.authorize_url("the-state", None)

        query = parse_qs(urlparse(url).query)
        self.assertTrue(url.startswith("https://www.facebook.com/v25.0/dialog/oauth?"))
        self.assertEqual(query["client_id"], ["test-app-id"])
        self.assertEqual(query["redirect_uri"], ["http://localhost:5173/api/social/instagram/callback"])
        self.assertEqual(
            query["scope"], ["instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"]
        )
        self.assertNotIn("code_challenge", query)

    def test_the_code_becomes_the_token_of_the_linked_page(self):
        # Given: Facebook swaps the code, extends the token and lists the Pages
        double = FacebookDouble(pages=[PAGE_WITHOUT_INSTAGRAM, PAGE])
        self.http.side_effect = double

        # When: the code is exchanged
        bundle = self.provider.exchange_code("the-code", None)

        # Then: the stored token is the Page's, which does not expire and has nothing to refresh with
        self.assertEqual(bundle.access_token, PAGE_TOKEN)
        self.assertIsNone(bundle.refresh_token)
        self.assertIsNone(bundle.expires_in)
        exchange = double.calls[1][2]["params"]
        self.assertEqual(exchange["grant_type"], "fb_exchange_token")
        self.assertEqual(exchange["fb_exchange_token"], USER_TOKEN)
        self.assertEqual(double.calls[2][2]["headers"], {"Authorization": f"OAuth {LONG_USER_TOKEN}"})

    def test_pages_granted_one_by_one_are_found_through_the_token(self):
        # Given: a Page in a business portfolio, which me/accounts does not list
        double = FacebookDouble(pages=[], granted_pages=["1000"], page_by_id={"1000": PAGE})
        self.http.side_effect = double

        # When: the code is exchanged
        bundle = self.provider.exchange_code("the-code", None)

        # Then: the Page is found through the grant, asked about with the app's token
        self.assertEqual(bundle.access_token, PAGE_TOKEN)
        debug = next(call for call in double.calls if call[1].endswith("/debug_token"))
        self.assertEqual(debug[2]["headers"], {"Authorization": "OAuth test-app-id|test-instagram-secret-DO-NOT-LEAK"})

    def test_granted_assets_that_are_not_pages_are_skipped(self):
        # Given: the grant lists the Instagram account before the Page, and an
        # Instagram account has no access_token field
        double = FacebookDouble(
            pages=[], granted_instagram=["17841400000000001"], granted_pages=["1000"], page_by_id={"1000": PAGE}
        )
        self.http.side_effect = double

        # When: the code is exchanged
        bundle = self.provider.exchange_code("the-code", None)

        # Then: the Instagram account is passed over and the Page is used
        self.assertEqual(bundle.access_token, PAGE_TOKEN)

    def test_no_linked_instagram_account_is_a_clear_refusal(self):
        self.http.side_effect = FacebookDouble(pages=[PAGE_WITHOUT_INSTAGRAM])

        with self.assertRaises(ProviderError) as raised:
            self.provider.exchange_code("the-code", None)
        self.assertIn("No Instagram professional account", raised.exception.message)

    def test_the_identity_is_the_instagram_account_of_the_page(self):
        self.http.side_effect = [
            FakeResponse(
                200,
                {
                    "id": "1000",
                    "instagram_business_account": {
                        "id": "17841400000000001",
                        "username": "a.creator",
                        "profile_picture_url": "https://example.com/a.jpg",
                    },
                },
            )
        ]

        identity = self.provider.fetch_identity(PAGE_TOKEN)

        self.assertEqual((identity.external_id, identity.display_name), ("17841400000000001", "a.creator"))
        self.assertEqual(identity.extra, {"page_id": "1000"})

    def test_an_instagram_connection_cannot_be_refreshed(self):
        with self.assertRaises(ProviderError) as raised:
            self.provider.refresh("")
        self.assertFalse(raised.exception.transient)

    def test_revoking_removes_the_apps_permissions_with_the_apps_token(self):
        double = FacebookDouble()
        self.http.side_effect = double

        self.provider.revoke(PAGE_TOKEN, "")

        method, url, kwargs = double.calls[-1]
        self.assertEqual((method, url), ("DELETE", f"{GRAPH_ROOT}/555/permissions"))
        self.assertEqual(kwargs["headers"], {"Authorization": "OAuth test-app-id|test-instagram-secret-DO-NOT-LEAK"})

    def test_a_refused_code_is_a_provider_error_without_the_secret(self):
        self.http.side_effect = [
            FakeResponse(400, {"error": {"message": "This authorization code has expired.", "code": 100}})
        ]

        with self.assertRaises(ProviderError) as raised:
            self.provider.exchange_code("the-code", None)
        self.assertNotIn("DO-NOT-LEAK", raised.exception.message)

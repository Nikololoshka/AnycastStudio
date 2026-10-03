from urllib.parse import parse_qs, urlparse

from platforms2.core import AuthToken, PlatformError, PlatformFailure
from platforms2.instagram import InstagramConfig
from platforms2.instagram.auth import InstagramAuthorizationInteractor
from platforms2.instagram.core import InstagramEndpoints, InstagramHttp

from ..base import REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer

SECRET = "app-secret-DO-NOT-LEAK"
CONFIG = InstagramConfig("app-id", SECRET, REDIRECT.format(platform="instagram"))
LINKED_PAGE = {"id": "page-1", "access_token": "page-token", "instagram_business_account": {"id": "ig-1"}}
BARE_PAGE = {"id": "page-2", "access_token": "other-token"}


def granted(*asset_ids: str, user_id: str = "fb-user-1") -> FakeAnswer:
    return ok({"data": {"user_id": user_id, "granular_scopes": [{"scope": "pages_show_list", "target_ids": list(asset_ids)}]}})


class InstagramAuthorizationScenarios(PlatformTestCase):
    def authorization(self) -> InstagramAuthorizationInteractor:
        return InstagramAuthorizationInteractor(CONFIG, InstagramHttp(self.http))

    def test_the_consent_url_asks_facebook_for_the_publishing_scopes(self):
        # Given / When: a consent request is created
        request = self.authorization().create_auth_request("the-state")

        # Then: Facebook gets the app, the comma-joined scopes and no PKCE
        query = parse_qs(urlparse(request.url).query)
        self.assertTrue(request.url.startswith(InstagramEndpoints.AUTHORIZE))
        self.assertEqual(query["client_id"], ["app-id"])
        self.assertEqual(query["scope"], [",".join(CONFIG.scopes)])
        self.assertNotIn("code_challenge", query)
        self.assertEqual(request.code_verifier, "")

    async def test_the_code_becomes_the_token_of_the_linked_page(self):
        # Given: the code becomes a short-lived token, then a long-lived one, and a linked page is listed
        self.given_answers(
            ok({"access_token": "short"}),
            ok({"access_token": "long"}),
            ok({"data": [BARE_PAGE, LINKED_PAGE]}),
        )

        # When: the code is exchanged
        token = await self.authorization().create_auth_token("the-code", "")

        # Then: the token is the page's, and each exchange carried the app's credentials
        self.assertEqual(token.access_token, "page-token")
        self.assertIsNone(token.refresh_token)
        self.assertEqual(self.http.sent[0].params["code"], "the-code")
        self.assertEqual(self.http.sent[1].params["fb_exchange_token"], "short")
        self.assertEqual(self.http.sent[2].headers["Authorization"], "OAuth long")

    async def test_pages_granted_one_by_one_are_found_through_the_token(self):
        # Given: the page list is empty, but the token names the granted pages
        self.given_answers(
            ok({"access_token": "short"}),
            ok({"access_token": "long"}),
            ok({"data": []}),
            granted("page-1"),
            ok(LINKED_PAGE),
        )

        # When: the code is exchanged
        token = await self.authorization().create_auth_token("the-code", "")

        # Then: the granted page was asked for directly, and the token was inspected with the app's token
        self.assertEqual(token.access_token, "page-token")
        self.assertEqual(self.http.sent[3].headers["Authorization"], f"OAuth app-id|{SECRET}")
        self.assertEqual(self.http.sent[4].url, InstagramEndpoints.node("page-1"))

    async def test_granted_assets_that_are_not_pages_are_skipped(self):
        self.given_answers(
            ok({"access_token": "short"}),
            ok({"access_token": "long"}),
            ok({"data": []}),
            granted("business-1", "page-1"),
            FakeAnswer(400, {"error": {"code": 100, "message": "Not a page"}}),
            ok(LINKED_PAGE),
        )

        token = await self.authorization().create_auth_token("the-code", "")

        self.assertEqual(token.access_token, "page-token")

    async def test_no_linked_instagram_account_is_a_clear_refusal(self):
        self.given_answers(ok({"access_token": "short"}), ok({"access_token": "long"}), ok({"data": [BARE_PAGE]}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().create_auth_token("the-code", "")

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)
        self.assertIn("professional account", raised.exception.message)

    async def test_a_refused_code_carries_facebooks_words_without_the_secret(self):
        self.given_answers(FakeAnswer(400, {"error": {"code": 100, "message": "Invalid verification code"}}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().create_auth_token("the-code", "")

        self.assertIn("Invalid verification code", raised.exception.message)
        self.assertNotIn(SECRET, raised.exception.message)

    async def test_the_profile_is_the_instagram_account_of_the_page(self):
        account = {"id": "ig-1", "username": "creator", "name": "A Creator", "profile_picture_url": "https://ig/a.jpg"}
        self.given_answers(ok({"id": "page-1", "instagram_business_account": account}))

        profile = await self.authorization().fetch_auth_profile("page-token")

        self.assertEqual((profile.external_id, profile.display_name, profile.avatar_url), ("ig-1", "creator", "https://ig/a.jpg"))
        self.assertEqual(self.http.last.headers["Authorization"], "OAuth page-token")

    async def test_a_page_without_an_instagram_account_is_refused(self):
        self.given_answers(ok({"id": "page-1"}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().fetch_auth_profile("page-token")

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)

    async def test_an_instagram_connection_cannot_be_refreshed(self):
        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("")

        self.assertEqual(raised.exception.failure, PlatformFailure.GRANT_REVOKED)
        self.assertEqual(self.http.sent, [])

    async def test_revoking_removes_the_apps_permissions_with_the_apps_token(self):
        # Given: Facebook says whose token it is, then removes the permissions
        self.given_answers(granted(user_id="fb-user-1"), ok({"success": True}))

        # When: the token is revoked
        await self.authorization().revoke_auth_token(AuthToken("page-token"))

        # Then: the user's permissions were deleted with the app's token
        self.assertEqual(self.http.last.method, "DELETE")
        self.assertEqual(self.http.last.url, InstagramEndpoints.permissions("fb-user-1"))
        self.assertEqual(self.http.last.headers["Authorization"], f"OAuth app-id|{SECRET}")

    async def test_a_token_nobody_owns_cannot_be_revoked(self):
        self.given_answers(ok({"data": {}}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().revoke_auth_token(AuthToken("page-token"))

        self.assertEqual(raised.exception.failure, PlatformFailure.UNEXPECTED)

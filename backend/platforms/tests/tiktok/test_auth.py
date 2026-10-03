from urllib.parse import parse_qs, urlparse

from platforms.core import AuthToken, Pkce, PlatformError, PlatformFailure
from platforms.tiktok import TikTokConfig
from platforms.tiktok.auth import TikTokAuthorizationInteractor
from platforms.tiktok.core import TikTokEndpoints, TikTokHttp

from ..base import REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer

SECRET = "client-secret-DO-NOT-LEAK"
CONFIG = TikTokConfig("client-key", SECRET, REDIRECT.format(platform="tiktok"))
TOKEN = {
    "access_token": "act.fresh",
    "refresh_token": "rft.rotated",
    "expires_in": 86400,
    "open_id": "open-id-1",
    "scope": "user.info.basic,video.publish",
    "token_type": "Bearer",
}
USER = {
    "data": {"user": {"open_id": "open-id-1", "display_name": "A Creator", "avatar_url": "https://example.com/a.jpg"}},
    "error": {"code": "ok", "message": "", "log_id": "log"},
}


class TikTokAuthorizationScenarios(PlatformTestCase):
    def authorization(self) -> TikTokAuthorizationInteractor:
        return TikTokAuthorizationInteractor(CONFIG, TikTokHttp(self.http))

    def test_the_consent_url_carries_the_client_key_and_a_hex_challenge(self):
        # Given / When: a consent request is created
        request = self.authorization().create_auth_request("the-state")

        # Then: TikTok gets its own parameter names and its hex encoding of the challenge
        query = parse_qs(urlparse(request.url).query)
        self.assertTrue(request.url.startswith(TikTokEndpoints.AUTHORIZE))
        self.assertEqual(query["client_key"], ["client-key"])
        self.assertEqual(query["scope"], ["user.info.basic,video.publish"])
        self.assertEqual(query["state"], ["the-state"])
        self.assertEqual(query["code_challenge"], [Pkce(request.code_verifier).hex_challenge()])
        self.assertEqual(query["redirect_uri"], ["http://localhost:5173/api/social/tiktok/callback"])

    async def test_the_code_is_exchanged_with_the_secret_and_the_verifier(self):
        # Given: TikTok issues tokens
        self.given_answers(ok(TOKEN))

        # When: the code is exchanged
        token = await self.authorization().create_auth_token("the-code", "the-verifier")

        # Then: the form carried what TikTok requires, and the scopes are split on commas
        sent = self.http.last.data
        self.assertEqual(sent["client_key"], "client-key")
        self.assertEqual(sent["client_secret"], SECRET)
        self.assertEqual(sent["code_verifier"], "the-verifier")
        self.assertEqual(token.access_token, "act.fresh")
        self.assertEqual(token.scopes, ("user.info.basic", "video.publish"))

    async def test_a_refresh_returns_the_rotated_refresh_token(self):
        self.given_answers(ok(TOKEN))

        token = await self.authorization().refresh_auth_token("rft.old")

        self.assertEqual(token.refresh_token, "rft.rotated")
        self.assertEqual(self.http.last.data["grant_type"], "refresh_token")

    async def test_a_refused_grant_says_the_account_must_be_reconnected(self):
        # Given: TikTok answers a 200 with an OAuth error body
        self.given_answers(ok({"error": "invalid_grant", "error_description": "Refresh token expired"}))

        # When / Then: the refusal is final and keeps TikTok's words
        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("rft.old")
        self.assertEqual(raised.exception.failure, PlatformFailure.GRANT_REVOKED)
        self.assertFalse(raised.exception.transient)
        self.assertIn("Refresh token expired", raised.exception.message)
        self.assertNotIn(SECRET, raised.exception.message)

    async def test_the_profile_is_the_open_id(self):
        self.given_answers(ok(USER))

        profile = await self.authorization().fetch_auth_profile("act.fresh")

        self.assertEqual((profile.external_id, profile.display_name), ("open-id-1", "A Creator"))
        self.assertEqual(self.http.last.headers["Authorization"], "Bearer act.fresh")

    async def test_an_error_inside_a_successful_response_is_a_refusal(self):
        # Given: TikTok answers a 200 whose error envelope says the token is invalid
        self.given_answers(ok({"data": {}, "error": {"code": "access_token_invalid", "message": "Token expired"}}))

        # When / Then: the envelope wins over the status
        with self.assertRaises(PlatformError) as raised:
            await self.authorization().fetch_auth_profile("act.old")
        self.assertEqual(raised.exception.failure, PlatformFailure.TOKEN_REJECTED)
        self.assertIn("Token expired", raised.exception.message)

    async def test_revoking_sends_the_access_token(self):
        self.given_answers(ok())

        await self.authorization().revoke_auth_token(AuthToken("act.fresh", "rft.rotated"))

        self.assertEqual(self.http.last.data["token"], "act.fresh")
        self.assertEqual(self.http.last.data["client_key"], "client-key")

    async def test_a_refused_revocation_is_reported(self):
        self.given_answers(FakeAnswer(400, {"error": "invalid_request", "error_description": "Bad token"}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().revoke_auth_token(AuthToken("act.fresh"))

        self.assertIn("Bad token", raised.exception.message)

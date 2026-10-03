from urllib.parse import parse_qs, urlparse

import aiohttp

from platforms.core import AuthToken, Pkce, PlatformError, PlatformFailure
from platforms.x import XConfig
from platforms.x.auth import XAuthorizationInteractor
from platforms.x.core import XEndpoints, XHttp

from ..base import REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer

SECRET = "x-secret-DO-NOT-LEAK"
CONFIG = XConfig("x-client-id", SECRET, REDIRECT.format(platform="x"))
TOKEN = {
    "token_type": "bearer",
    "access_token": "x.access",
    "refresh_token": "x.refresh-rotated",
    "expires_in": 7200,
    "scope": "tweet.read tweet.write users.read media.write offline.access",
}


class XAuthorizationScenarios(PlatformTestCase):
    def authorization(self) -> XAuthorizationInteractor:
        return XAuthorizationInteractor(CONFIG, XHttp(self.http))

    def test_the_consent_url_carries_the_scopes_and_a_base64url_challenge(self):
        request = self.authorization().create_auth_request("the-state")

        query = parse_qs(urlparse(request.url).query)
        self.assertTrue(request.url.startswith(XEndpoints.AUTHORIZE))
        self.assertEqual(query["client_id"], ["x-client-id"])
        self.assertEqual(query["scope"], [" ".join(CONFIG.scopes)])
        self.assertEqual(query["code_challenge"], [Pkce(request.code_verifier).challenge()])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertNotIn(SECRET, request.url)

    async def test_the_code_is_exchanged_with_basic_client_auth_and_the_verifier(self):
        # Given: X issues tokens
        self.given_answers(ok(TOKEN))

        # When: the code is exchanged
        token = await self.authorization().create_auth_token("the-code", "the-verifier")

        # Then: the client authenticated with Basic auth, and the secret stayed out of the form
        sent = self.http.last
        self.assertEqual(sent.kwargs["auth"], aiohttp.BasicAuth("x-client-id", SECRET))
        self.assertEqual(sent.data["code_verifier"], "the-verifier")
        self.assertNotIn("client_secret", sent.data)
        self.assertEqual(token.scopes, tuple(TOKEN["scope"].split()))

    async def test_a_refresh_returns_the_rotated_refresh_token(self):
        self.given_answers(ok(TOKEN))

        token = await self.authorization().refresh_auth_token("x.refresh-old")

        self.assertEqual(token.refresh_token, "x.refresh-rotated")

    async def test_a_used_refresh_token_says_the_account_must_be_reconnected(self):
        # Given: X answers that the refresh token was invalid
        self.given_answers(FakeAnswer(400, {"error": "invalid_request", "error_description": "Value passed for the token was invalid."}))

        # When / Then: that is a revoked grant, not misconfiguration
        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("x.refresh-old")
        self.assertEqual(raised.exception.failure, PlatformFailure.GRANT_REVOKED)
        self.assertNotIn(SECRET, raised.exception.message)

    async def test_a_wrong_client_is_misconfiguration(self):
        self.given_answers(FakeAnswer(401, {"error": "unauthorized_client", "error_description": "Missing valid authorization header"}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("x.refresh-old")

        self.assertEqual(raised.exception.failure, PlatformFailure.MISCONFIGURED)

    async def test_the_profile_is_the_user_id_named_by_the_username(self):
        self.given_answers(ok({"data": {"id": "2244994945", "username": "creator", "name": "A Creator", "profile_image_url": "https://x/a.jpg"}}))

        profile = await self.authorization().fetch_auth_profile("x.access")

        self.assertEqual((profile.external_id, profile.display_name, profile.avatar_url), ("2244994945", "creator", "https://x/a.jpg"))
        self.assertEqual(self.http.last.headers["Authorization"], "Bearer x.access")

    async def test_revoking_ends_the_refresh_token_and_the_access_token(self):
        self.given_answers(ok({"revoked": True}), ok({"revoked": True}))

        await self.authorization().revoke_auth_token(AuthToken("x.access", "x.refresh"))

        self.assertEqual(
            [(sent.data["token"], sent.data["token_type_hint"]) for sent in self.http.sent],
            [("x.refresh", "refresh_token"), ("x.access", "access_token")],
        )

    async def test_a_failed_revocation_still_revokes_the_other_token(self):
        # Given: X refuses to revoke the refresh token
        self.given_answers(FakeAnswer(503), ok({"revoked": True}))

        # When / Then: the access token is still revoked, and the refusal is reported
        with self.assertRaises(PlatformError) as raised:
            await self.authorization().revoke_auth_token(AuthToken("x.access", "x.refresh"))
        self.assertEqual(len(self.http.sent), 2)
        self.assertEqual(raised.exception.failure, PlatformFailure.NETWORK)

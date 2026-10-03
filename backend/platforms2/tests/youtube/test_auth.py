from urllib.parse import parse_qs, urlparse

from platforms2.core import AuthToken, Pkce, PlatformError, PlatformFailure
from platforms2.youtube import YouTubeConfig
from platforms2.youtube.auth import YouTubeAuthorizationInteractor
from platforms2.youtube.core import GoogleEndpoints, GoogleHttp

from ..base import REDIRECT, PlatformTestCase, ok
from ..fakes.http import FakeAnswer

SECRET = "client-secret-DO-NOT-LEAK"
CONFIG = YouTubeConfig("client-id", SECRET, REDIRECT.format(platform="youtube"))
TOKEN = {
    "access_token": "ya29.fresh",
    "refresh_token": "1//refresh",
    "expires_in": 3599,
    "scope": "https://www.googleapis.com/auth/youtube",
}
CHANNELS = {
    "items": [
        {"id": "UC123", "snippet": {"title": "My channel", "thumbnails": {"default": {"url": "https://yt/a.jpg"}}}}
    ]
}


class YouTubeAuthorizationScenarios(PlatformTestCase):
    def authorization(self) -> YouTubeAuthorizationInteractor:
        return YouTubeAuthorizationInteractor(CONFIG, GoogleHttp(self.http))

    def test_the_consent_url_asks_for_offline_access_with_a_challenge(self):
        # Given / When: a consent request is created
        request = self.authorization().create_auth_request("the-state")

        # Then: Google gets the client, the scopes, the S256 challenge of the kept verifier and offline access
        query = parse_qs(urlparse(request.url).query)
        self.assertTrue(request.url.startswith(GoogleEndpoints.AUTHORIZE))
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["redirect_uri"], ["http://localhost:5173/api/social/youtube/callback"])
        self.assertEqual(query["state"], ["the-state"])
        self.assertEqual(query["code_challenge"], [Pkce(request.code_verifier).challenge()])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertNotIn(SECRET, request.url)

    async def test_the_code_is_exchanged_with_the_secret_and_the_verifier(self):
        # Given: Google issues tokens
        self.given_answers(ok(TOKEN))

        # When: the code is exchanged
        token = await self.authorization().create_auth_token("the-code", "the-verifier")

        # Then: the form carried the grant, and the token came back with its scopes
        sent = self.http.last.data
        self.assertEqual(sent["client_secret"], SECRET)
        self.assertEqual(sent["code_verifier"], "the-verifier")
        self.assertEqual(sent["grant_type"], "authorization_code")
        self.assertEqual(token.access_token, "ya29.fresh")
        self.assertEqual(token.refresh_token, "1//refresh")
        self.assertEqual(token.scopes, ("https://www.googleapis.com/auth/youtube",))

    async def test_a_refresh_without_a_new_refresh_token_returns_none_for_it(self):
        self.given_answers(ok({"access_token": "ya29.next", "expires_in": 3599}))

        token = await self.authorization().refresh_auth_token("1//refresh")

        self.assertEqual(token.access_token, "ya29.next")
        self.assertIsNone(token.refresh_token)
        self.assertEqual(token.scopes, CONFIG.scopes)

    async def test_a_revoked_grant_says_the_account_must_be_reconnected(self):
        # Given: Google says the refresh token is no longer valid
        self.given_answers(FakeAnswer(400, {"error": "invalid_grant", "error_description": "Token revoked"}))

        # When / Then: the failure is a revoked grant, with Google's words and without the secret
        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("1//refresh")
        self.assertEqual(raised.exception.failure, PlatformFailure.GRANT_REVOKED)
        self.assertIn("Token revoked", raised.exception.message)
        self.assertNotIn(SECRET, raised.exception.message)

    async def test_a_wrong_client_is_misconfiguration(self):
        self.given_answers(FakeAnswer(401, {"error": "invalid_client"}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("1//refresh")

        self.assertEqual(raised.exception.failure, PlatformFailure.MISCONFIGURED)

    async def test_a_google_outage_is_transient(self):
        self.given_answers(FakeAnswer(503, {"error": "backendError"}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().refresh_auth_token("1//refresh")

        self.assertTrue(raised.exception.transient)

    async def test_the_profile_is_the_first_channel(self):
        # Given: the account has a channel
        self.given_answers(ok(CHANNELS))

        # When: the profile is fetched
        profile = await self.authorization().fetch_auth_profile("ya29.token")

        # Then: it is the channel, asked for with the bearer token in a header
        self.assertEqual((profile.external_id, profile.display_name, profile.avatar_url), ("UC123", "My channel", "https://yt/a.jpg"))
        self.assertEqual(self.http.last.headers["Authorization"], "Bearer ya29.token")
        self.assertEqual(self.http.last.params, {"part": "snippet", "mine": "true"})

    async def test_an_account_without_a_channel_is_refused(self):
        self.given_answers(ok({"items": []}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().fetch_auth_profile("ya29.token")

        self.assertEqual(raised.exception.failure, PlatformFailure.REFUSED)

    async def test_a_string_error_from_google_is_reported_not_crashed_on(self):
        self.given_answers(FakeAnswer(401, {"error": "invalid_token"}))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().fetch_auth_profile("ya29.token")

        self.assertIn("invalid_token", raised.exception.message)

    async def test_revoking_ends_the_refresh_token(self):
        self.given_answers(ok())

        await self.authorization().revoke_auth_token(AuthToken("ya29.token", "1//refresh"))

        self.assertEqual(self.http.last.data, {"token": "1//refresh"})

    async def test_revoking_without_a_refresh_token_ends_the_access_token(self):
        self.given_answers(ok())

        await self.authorization().revoke_auth_token(AuthToken("ya29.token"))

        self.assertEqual(self.http.last.data, {"token": "ya29.token"})

    async def test_an_already_invalid_token_counts_as_revoked(self):
        self.given_answers(FakeAnswer(400, {"error": "invalid_token"}))

        await self.authorization().revoke_auth_token(AuthToken("ya29.token", "1//refresh"))

    async def test_a_refused_revocation_is_reported(self):
        self.given_answers(FakeAnswer(503))

        with self.assertRaises(PlatformError) as raised:
            await self.authorization().revoke_auth_token(AuthToken("ya29.token", "1//refresh"))

        self.assertEqual(raised.exception.failure, PlatformFailure.NETWORK)

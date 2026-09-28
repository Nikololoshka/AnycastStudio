from urllib.parse import parse_qs, urlparse

from django.test import override_settings

from config.wiring import container
from platforms.core.auth import Pkce
from platforms.core.errors import ProviderError
from platforms.x import XProvider
from platforms.x.oauth import REVOKE_ENDPOINT, TOKEN_ENDPOINT

from .base import FakeResponse, PlatformTestCase

TOKEN = {
    "token_type": "bearer",
    "expires_in": 7200,
    "access_token": "x.fresh",
    "refresh_token": "x.rotated",
    "scope": "tweet.read tweet.write users.read media.write offline.access",
}
USER = {"data": {"id": "2244994945", "name": "A Creator", "username": "a_creator", "profile_image_url": "https://pbs.twimg.com/a.jpg"}}


@override_settings(X_CLIENT_ID="client-id", X_CLIENT_SECRET="client-secret", PUBLIC_REDIRECT_ORIGIN="http://localhost:5173")
class XOAuthScenarios(PlatformTestCase):
    def test_the_consent_url_carries_the_scopes_and_a_base64url_challenge(self):
        # Given: a verifier kept on the server
        provider = XProvider.create(container().config)
        verifier = Pkce.generate().verifier

        # When: the consent URL is built
        url = provider.authorize_url("the-state", provider.code_challenge(verifier))

        # Then: X gets the standard S256 challenge and every scope, space-separated
        query = parse_qs(urlparse(url).query)
        self.assertTrue(url.startswith("https://x.com/i/oauth2/authorize?"))
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["scope"], ["tweet.read tweet.write users.read media.write offline.access"])
        self.assertEqual(query["code_challenge"], [Pkce(verifier).challenge()])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["redirect_uri"], ["http://localhost:5173/api/social/x/callback"])
        self.assertNotIn("client-secret", url)

    def test_the_code_is_exchanged_with_basic_client_auth_and_the_verifier(self):
        # Given: X issues tokens
        self.http.side_effect = [FakeResponse(200, TOKEN)]

        # When: the code is exchanged
        bundle = XProvider.create(container().config).exchange_code("the-code", "the-verifier")

        # Then: the secret travels in the Basic header, never in the form
        call = self.http.call_args
        self.assertEqual(call.args[1], TOKEN_ENDPOINT)
        self.assertEqual(call.kwargs["auth"], ("client-id", "client-secret"))
        self.assertNotIn("client_secret", call.kwargs["data"])
        self.assertEqual(call.kwargs["data"]["code_verifier"], "the-verifier")
        self.assertEqual(call.kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(bundle.access_token, "x.fresh")
        self.assertEqual(bundle.expires_in, 7200)
        self.assertIn("media.write", bundle.scopes)

    def test_a_refresh_returns_the_rotated_refresh_token(self):
        self.http.side_effect = [FakeResponse(200, TOKEN)]

        bundle = XProvider.create(container().config).refresh("x.old")

        self.assertEqual(bundle.refresh_token, "x.rotated")
        self.assertEqual(self.http.call_args.kwargs["data"]["refresh_token"], "x.old")

    def test_a_used_refresh_token_is_not_reported_as_transient(self):
        # Given: X refuses a refresh token that was already used
        refusal = {"error": "invalid_request", "error_description": "Value passed for the token was invalid."}
        self.http.side_effect = [FakeResponse(400, refusal)]

        # When / Then: the refusal says the account must be reconnected, in X's words
        with self.assertRaises(ProviderError) as raised:
            XProvider.create(container().config).refresh("x.used")
        self.assertFalse(raised.exception.transient)
        self.assertIn("token was invalid", raised.exception.message)

    def test_the_identity_is_the_user_id_named_by_the_username(self):
        self.http.side_effect = [FakeResponse(200, USER)]

        identity = XProvider.create(container().config).fetch_identity("x.fresh")

        self.assertEqual((identity.external_id, identity.display_name), ("2244994945", "a_creator"))
        self.assertEqual(identity.avatar_url, "https://pbs.twimg.com/a.jpg")
        self.assertEqual(self.http.call_args.kwargs["headers"], {"Authorization": "Bearer x.fresh"})

    def test_revoking_ends_the_refresh_token_and_the_access_token(self):
        self.http.side_effect = [FakeResponse(200, {"revoked": True}), FakeResponse(200, {"revoked": True})]

        XProvider.create(container().config).revoke("x.access", "x.refresh")

        sent = [(call.args[1], call.kwargs["data"]["token"], call.kwargs["data"]["token_type_hint"]) for call in self.http.call_args_list]
        self.assertEqual(
            sent, [(REVOKE_ENDPOINT, "x.refresh", "refresh_token"), (REVOKE_ENDPOINT, "x.access", "access_token")]
        )

    def test_a_failed_revocation_still_revokes_the_other_token(self):
        self.http.side_effect = [FakeResponse(400, {"error": "invalid_request"}), FakeResponse(200, {"revoked": True})]

        with self.assertRaises(ProviderError):
            XProvider.create(container().config).revoke("x.access", "x.refresh")
        self.assertEqual(self.http.call_count, 2)

    @override_settings(X_CLIENT_SECRET="")
    def test_a_missing_secret_is_reported_before_anything_is_sent(self):
        with self.assertRaises(ProviderError):
            XProvider.create(container().config).exchange_code("the-code", "the-verifier")
        self.http.assert_not_called()

    def test_the_secret_never_reaches_a_log(self):
        self.http.side_effect = [FakeResponse(503, {})] * 3

        with self.assertLogs("platforms", level="DEBUG") as logs, self.assertRaises(ProviderError):
            XProvider.create(container().config).refresh("x.old")
        self.assertFalse(any("client-secret" in line or "x.old" in line for line in logs.output))

from urllib.parse import parse_qs, urlparse

from django.test import override_settings

from config.wiring import container
from platforms.core.auth import Pkce
from platforms.core.errors import ProviderError
from platforms.tiktok.auth import TikTokProvider

from ..base import FakeResponse, PlatformTestCase

TOKEN = {
    "access_token": "act.fresh",
    "refresh_token": "rft.rotated",
    "expires_in": 86400,
    "refresh_expires_in": 31536000,
    "open_id": "open-id-1",
    "scope": "user.info.basic,video.publish",
    "token_type": "Bearer",
}
USER = {
    "data": {"user": {"open_id": "open-id-1", "display_name": "A Creator", "avatar_url": "https://example.com/a.jpg"}},
    "error": {"code": "ok", "message": "", "log_id": "log"},
}


@override_settings(TIKTOK_CLIENT_KEY="client-key", TIKTOK_CLIENT_SECRET="client-secret", PUBLIC_REDIRECT_ORIGIN="http://localhost:5173")
class TikTokOAuthScenarios(PlatformTestCase):
    def test_the_consent_url_carries_the_client_key_and_a_hex_challenge(self):
        # Given: a verifier kept on the server
        provider = TikTokProvider.create(container().config)
        verifier = Pkce.generate().verifier

        # When: the consent URL is built
        query = parse_qs(urlparse(provider.authorize_url("the-state", provider.code_challenge(verifier))).query)

        # Then: TikTok gets its own parameter names and its hex encoding of the challenge
        self.assertEqual(query["client_key"], ["client-key"])
        self.assertEqual(query["scope"], ["user.info.basic,video.publish"])
        self.assertEqual(query["state"], ["the-state"])
        self.assertEqual(query["code_challenge"], [Pkce(verifier).hex_challenge()])
        self.assertEqual(query["redirect_uri"], ["http://localhost:5173/api/social/tiktok/callback"])

    def test_the_code_is_exchanged_with_the_secret_and_the_verifier(self):
        # Given: TikTok issues tokens
        self.http.side_effect = [FakeResponse(200, TOKEN)]

        # When: the code is exchanged
        bundle = TikTokProvider.create(container().config).exchange_code("the-code", "the-verifier")

        # Then: the form carried what TikTok requires, and the scopes are split on commas
        sent = self.http.call_args.kwargs["data"]
        self.assertEqual(sent["client_secret"], "client-secret")
        self.assertEqual(sent["code_verifier"], "the-verifier")
        self.assertEqual(bundle.access_token, "act.fresh")
        self.assertEqual(bundle.scopes, ("user.info.basic", "video.publish"))

    def test_a_refused_code_is_not_reported_as_transient(self):
        # Given: TikTok answers with an OAuth error body
        self.http.side_effect = [FakeResponse(200, {"error": "invalid_grant", "error_description": "Code expired"})]

        # When / Then: the refusal says the account must be reconnected
        with self.assertRaises(ProviderError) as raised:
            TikTokProvider.create(container().config).refresh("rft.old")
        self.assertFalse(raised.exception.transient)

    def test_a_refresh_returns_the_rotated_refresh_token(self):
        self.http.side_effect = [FakeResponse(200, TOKEN)]

        bundle = TikTokProvider.create(container().config).refresh("rft.old")

        self.assertEqual(bundle.refresh_token, "rft.rotated")

    def test_the_identity_is_the_open_id(self):
        self.http.side_effect = [FakeResponse(200, USER)]

        identity = TikTokProvider.create(container().config).fetch_identity("act.fresh")

        self.assertEqual(identity.external_id, "open-id-1")
        self.assertEqual(identity.display_name, "A Creator")

    def test_an_error_inside_a_successful_response_is_a_refusal(self):
        # Given: TikTok answers 200 with an error envelope
        self.http.side_effect = [
            FakeResponse(200, {"data": {}, "error": {"code": "scope_not_authorized", "message": "No scope"}})
        ]

        # When / Then: it is not mistaken for an identity
        with self.assertRaises(ProviderError):
            TikTokProvider.create(container().config).fetch_identity("act.fresh")

    def test_revoking_sends_the_access_token(self):
        self.http.side_effect = [FakeResponse(200, {})]

        TikTokProvider.create(container().config).revoke("act.current", "rft.current")

        self.assertEqual(self.http.call_args.kwargs["data"]["token"], "act.current")

    @override_settings(TIKTOK_CLIENT_KEY="")
    def test_a_missing_client_key_is_reported_before_anything_is_sent(self):
        with self.assertRaises(ProviderError):
            TikTokProvider.create(container().config).authorize_url("state", "challenge")
        self.http.assert_not_called()

from django.test import override_settings

from config.wiring import container
from platforms.core.errors import ProviderError
from platforms.youtube import YouTubeProvider

from .base import FakeResponse, PlatformTestCase

TOKEN = {"access_token": "ya29.fresh", "expires_in": 3599, "scope": "https://www.googleapis.com/auth/youtube"}


@override_settings(YOUTUBE_CLIENT_ID="client-id", YOUTUBE_CLIENT_SECRET="client-secret")
class RefreshScenarios(PlatformTestCase):
    def test_a_passing_google_outage_does_not_cost_the_connection(self):
        # Given: Google fails once with a 503, then answers
        self.http.side_effect = [FakeResponse(503, {"error": "backendError"}), FakeResponse(200, TOKEN)]

        # When: the token is refreshed
        bundle = YouTubeProvider.create(container().config).refresh("1//refresh")

        # Then: the retry got the token, so the account is not marked for reconnecting
        self.assertEqual(bundle.access_token, "ya29.fresh")
        self.assertEqual(self.http.call_count, 2)

    def test_a_revoked_grant_is_not_retried(self):
        # Given: Google says the refresh token is no longer valid
        self.http.side_effect = [FakeResponse(400, {"error": "invalid_grant", "error_description": "Token revoked"})]

        # When / Then: that is final, and the reason is kept
        with self.assertRaisesMessage(ProviderError, "Token revoked"):
            YouTubeProvider.create(container().config).refresh("1//refresh")
        self.assertEqual(self.http.call_count, 1)


class IdentityScenarios(PlatformTestCase):
    def test_a_string_error_from_google_is_reported_not_crashed_on(self):
        # Given: Google answers the channel request with a bare error string
        self.http.side_effect = [FakeResponse(401, {"error": "invalid_token"})]

        # When / Then: it becomes a ProviderError the caller already handles
        with self.assertRaisesMessage(ProviderError, "invalid_token"):
            YouTubeProvider.create(container().config).fetch_identity("ya29.token")

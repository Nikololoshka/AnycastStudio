from urllib.parse import parse_qs, urlparse

from platforms.core.auth import Identity, OAuth2Provider
from platforms.core.config import HttpConfig, OAuthCredentials, PlatformConfig
from platforms.core.errors import ProviderError
from platforms.core.http import PlatformClient

from .base import FakeResponse, PlatformTestCase

TOKEN_ENDPOINT = "https://example.test/oauth/token"
REDIRECT_URI = "https://app.example.test/api/social/example/callback"


class ExampleProvider(OAuth2Provider):
    name = "example"
    label = "Example"
    scopes = ("video.read", "video.write")
    authorize_endpoint = "https://example.test/oauth/authorize"
    token_endpoint = TOKEN_ENDPOINT
    scope_separator = ","

    @classmethod
    def create(cls, config: PlatformConfig):
        return cls(PlatformClient(config.http, label=cls.label), config.credentials_of(cls.name), REDIRECT_URI)

    def fetch_identity(self, access_token: str) -> Identity:
        return Identity(external_id="1", display_name="Example")

    def revoke(self, access_token: str, refresh_token: str) -> None:
        return None


class NoPkceProvider(ExampleProvider):
    uses_pkce = False


def example(kind=ExampleProvider, client_id: str = "client-id"):
    credentials = OAuthCredentials("EXAMPLE_CLIENT_ID", "EXAMPLE_CLIENT_SECRET", client_id, "client-secret")
    return kind.create(PlatformConfig(http=HttpConfig(attempts=3), credentials={"example": credentials}))


class OAuth2ProviderScenarios(PlatformTestCase):
    def test_the_consent_url_carries_the_client_scopes_and_challenge(self):
        # When: the consent URL is built
        url = example().authorize_url("the-state", "the-challenge")

        # Then: it names the client, joins the scopes with the platform's separator and sends the challenge
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["scope"], ["video.read,video.write"])
        self.assertEqual(query["state"], ["the-state"])
        self.assertEqual(query["code_challenge"], ["the-challenge"])
        self.assertEqual(query["code_challenge_method"], ["S256"])

    def test_a_platform_without_pkce_sends_no_challenge(self):
        # When: the consent URL is built for a platform without PKCE
        query = parse_qs(urlparse(example(NoPkceProvider).authorize_url("the-state", None)).query)

        # Then: no challenge parameters are sent
        self.assertNotIn("code_challenge", query)
        self.assertNotIn("code_challenge_method", query)

    def test_granted_scopes_are_split_by_the_platform_separator(self):
        # Given: the platform grants scopes as a comma list with spaces
        self.http.return_value = FakeResponse(200, {"access_token": "a", "scope": "video.read, video.write"})

        # When: the code is exchanged
        bundle = example().exchange_code("code", "verifier")

        # Then: each scope is kept on its own
        self.assertEqual(bundle.scopes, ("video.read", "video.write"))

    def test_the_client_credentials_go_in_the_token_request(self):
        # Given: the platform issues a token
        self.http.return_value = FakeResponse(200, {"access_token": "a"})

        # When: the token is refreshed
        example().refresh("r")

        # Then: the client and the grant are in the form body
        sent = self.http.call_args.kwargs["data"]
        self.assertEqual(sent["client_id"], "client-id")
        self.assertEqual(sent["grant_type"], "refresh_token")
        self.assertEqual(sent["refresh_token"], "r")

    def test_an_answer_without_a_token_is_refused_with_the_reason(self):
        # Given: the platform answers 200 without a token
        self.http.return_value = FakeResponse(200, {"error": "invalid_request", "error_description": "Bad verifier"})

        # When / Then: the refusal names the platform and the reason
        with self.assertRaisesMessage(ProviderError, "Example refused the token request: Bad verifier"):
            example().exchange_code("code", "verifier")

    def test_a_malformed_token_answer_is_refused_without_repeating_the_token(self):
        # Given: the token arrives next to an expiry that is not a number
        self.http.return_value = FakeResponse(200, {"access_token": "secret-token", "expires_in": "soon"})

        # When: the code is exchanged
        with self.assertRaises(ProviderError) as raised:
            example().exchange_code("code", "verifier")

        # Then: the refusal is final and does not carry the token
        self.assertFalse(raised.exception.transient)
        self.assertNotIn("secret-token", raised.exception.message)

    def test_a_network_failure_is_transient(self):
        # Given: the platform is unavailable on every attempt
        self.http.return_value = FakeResponse(503)

        # When: the token is refreshed
        with self.assertRaises(ProviderError) as raised:
            example().refresh("r")

        # Then: the caller may try again later
        self.assertTrue(raised.exception.transient)


class MissingConfigurationScenarios(PlatformTestCase):
    def test_an_unconfigured_client_names_the_setting(self):
        # When / Then: the setting to fill in is named, and nothing is sent
        with self.assertRaisesMessage(ProviderError, "EXAMPLE_CLIENT_ID is not configured"):
            example(client_id="").authorize_url("the-state", "the-challenge")
        self.http.assert_not_called()

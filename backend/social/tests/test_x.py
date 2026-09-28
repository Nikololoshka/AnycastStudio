from urllib.parse import parse_qs, urlparse

from platforms.core.auth import Pkce
from platforms.x.oauth import TOKEN_ENDPOINT, USER_INFO_ENDPOINT
from social.models import OAuthSession
from social.tests.base import FakeResponse, SocialTestCase

CONNECT_URL = "/api/social/x/connect"
CALLBACK_URL = "/api/social/x/callback"

TOKEN = {
    "token_type": "bearer",
    "expires_in": 7200,
    "access_token": "x.access-DO-NOT-LEAK",
    "refresh_token": "x.refresh-DO-NOT-LEAK",
    "scope": "tweet.read tweet.write users.read media.write offline.access",
}
USER = {"data": {"id": "2244994945", "name": "A Creator", "username": "a_creator"}}


class XConnectScenarios(SocialTestCase):
    def started_state(self) -> str:
        auth_url = self.body(self.client.post(CONNECT_URL))["authUrl"]
        return parse_qs(urlparse(auth_url).query)["state"][0]

    def test_the_consent_url_carries_the_s256_challenge_of_the_stored_verifier(self):
        # Given: somebody is signed in
        self.sign_in()

        # When: they start connecting X
        auth_url = self.body(self.client.post(CONNECT_URL))["authUrl"]

        # Then: X gets the base64url challenge of the verifier we kept
        query = parse_qs(urlparse(auth_url).query)
        session = OAuthSession.objects.get()
        self.assertTrue(auth_url.startswith("https://x.com/i/oauth2/authorize?"))
        self.assertEqual(query["client_id"], ["test-x-client-id"])
        self.assertEqual(query["code_challenge"], [Pkce(session.code_verifier).challenge()])

    def test_a_completed_consent_connects_the_account(self):
        # Given: a connection was started and X issues tokens
        self.sign_in()
        state = self.started_state()
        verifier = OAuthSession.objects.get().code_verifier
        self.http.side_effect = [FakeResponse(payload=TOKEN), FakeResponse(payload=USER)]

        # When: X redirects back
        response = self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})

        # Then: the account is stored under the X user id, with both tokens
        self.assertIn("result=connected", response["Location"])
        account = self.only_account()
        self.assertEqual((account.platform, account.external_id, account.display_name), ("x", "2244994945", "a_creator"))
        self.assertEqual(account.refresh_token, "x.refresh-DO-NOT-LEAK")
        self.assertIsNotNone(account.token_expires_at)
        token_call, identity_call = self.http.call_args_list
        self.assertEqual(token_call.args[1], TOKEN_ENDPOINT)
        self.assertEqual(token_call.kwargs["data"]["code_verifier"], verifier)
        self.assertEqual(identity_call.args[1], USER_INFO_ENDPOINT)

    def test_the_tokens_are_not_sent_to_the_browser(self):
        self.sign_in()
        state = self.started_state()
        self.http.side_effect = [FakeResponse(payload=TOKEN), FakeResponse(payload=USER)]
        self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})

        content = self.client.get("/api/social/accounts").content.decode()

        self.assertIn("a_creator", content)
        self.assertNotIn("DO-NOT-LEAK", content)

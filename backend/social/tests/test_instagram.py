from urllib.parse import parse_qs, urlparse

from platforms.instagram.api import GRAPH_ROOT
from social.models import OAuthSession, SocialAccount
from social.tests.base import ACCOUNTS_URL, FakeResponse, SocialTestCase

CONNECT_URL = "/api/social/instagram/connect"
CALLBACK_URL = "/api/social/instagram/callback"

PAGE_TOKEN = "EAAG.page-token-DO-NOT-LEAK"
IG_USER_ID = "17841400000000001"
PAGE = {"id": "1000", "access_token": PAGE_TOKEN, "instagram_business_account": {"id": IG_USER_ID}}
IDENTITY = {
    "id": "1000",
    "instagram_business_account": {"id": IG_USER_ID, "username": "a.creator", "profile_picture_url": ""},
}


def connected_responses(pages) -> list[FakeResponse]:
    return [
        FakeResponse(payload={"access_token": "EAAG.short"}),
        FakeResponse(payload={"access_token": "EAAG.long"}),
        FakeResponse(payload={"data": pages}),
        FakeResponse(payload=IDENTITY),
    ]


class InstagramConnectScenarios(SocialTestCase):
    def started_state(self) -> str:
        auth_url = self.body(self.client.post(CONNECT_URL))["authUrl"]
        return parse_qs(urlparse(auth_url).query)["state"][0]

    def test_the_consent_url_goes_to_facebook_without_a_challenge(self):
        # Given: somebody is signed in
        self.sign_in()

        # When: they start connecting Instagram
        auth_url = self.body(self.client.post(CONNECT_URL))["authUrl"]

        # Then: Facebook Login is asked, and no verifier is kept for it
        self.assertTrue(auth_url.startswith("https://www.facebook.com/v25.0/dialog/oauth?"))
        self.assertNotIn("code_challenge", auth_url)
        self.assertEqual(OAuthSession.objects.get().code_verifier, "")

    def test_a_completed_consent_connects_the_instagram_account_of_the_page(self):
        # Given: a connection was started and Facebook lists a Page with an Instagram account
        self.sign_in()
        state = self.started_state()
        self.http.side_effect = connected_responses([PAGE])

        # When: Facebook redirects back
        response = self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})

        # Then: the Instagram account is stored with the Page token, which never expires
        self.assertIn("result=connected", response["Location"])
        account = self.only_account()
        self.assertEqual((account.platform, account.external_id), ("instagram", IG_USER_ID))
        self.assertEqual(account.display_name, "a.creator")
        self.assertEqual(account.access_token, PAGE_TOKEN)
        self.assertEqual(account.refresh_token, "")
        self.assertIsNone(account.token_expires_at)

    def test_a_person_without_a_linked_instagram_account_is_told_it_failed(self):
        self.sign_in()
        state = self.started_state()
        self.http.side_effect = connected_responses([{"id": "999", "access_token": "EAAG.other"}])

        response = self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})

        self.assertIn("result=failed", response["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_the_page_token_is_never_sent_to_the_browser(self):
        self.sign_in()
        state = self.started_state()
        self.http.side_effect = connected_responses([PAGE])
        self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})

        content = self.client.get(ACCOUNTS_URL).content.decode()

        self.assertNotIn(PAGE_TOKEN, content)

    def test_disconnecting_revokes_the_apps_permissions(self):
        # Given: a connected Instagram account, which holds no refresh token
        self.sign_in()
        state = self.started_state()
        self.http.side_effect = connected_responses([PAGE])
        self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})
        account = self.only_account()
        self.http.side_effect = [
            FakeResponse(payload={"data": {"user_id": "555"}}),
            FakeResponse(payload={"success": True}),
        ]

        # When: the person disconnects it
        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        # Then: Facebook is asked to drop the app's permissions, and the token is gone
        self.assertEqual(response.status_code, 200)
        method, url = self.http.call_args_list[-1].args[:2]
        self.assertEqual((method, url), ("DELETE", f"{GRAPH_ROOT}/555/permissions"))
        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.REVOKED)
        self.assertEqual(account.access_token, "")

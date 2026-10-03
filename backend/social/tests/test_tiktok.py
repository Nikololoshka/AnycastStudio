from urllib.parse import parse_qs, urlparse

from django.utils import timezone

from accounts.models import User
from platforms.core import Pkce
from social.models import OAuthSession, SocialAccount
from platforms.tests.fakes.http import FakeAnswer
from social.tests.base import SocialTestCase

CONNECT_URL = "/api/social/tiktok/connect"
CALLBACK_URL = "/api/social/tiktok/callback"

CREATOR = {
    "data": {
        "creator_username": "a.creator",
        "creator_nickname": "A Creator",
        "creator_avatar_url": "https://example.com/a.jpg",
        "privacy_level_options": ["SELF_ONLY", "FOLLOWER_OF_CREATOR"],
        "comment_disabled": True,
        "duet_disabled": False,
        "stitch_disabled": False,
        "max_video_post_duration_sec": 600,
    },
    "error": {"code": "ok", "message": "", "log_id": "log"},
}
TOKEN = {"access_token": "act.token", "refresh_token": "rft.token", "expires_in": 86400, "scope": "user.info.basic,video.publish"}
USER = {"data": {"user": {"open_id": "open-id-1", "display_name": "A Creator"}}, "error": {"code": "ok"}}


class TikTokConnectScenarios(SocialTestCase):
    def test_the_consent_url_carries_the_hex_challenge_of_the_stored_verifier(self):
        # Given: somebody is signed in
        self.sign_in()

        # When: they start connecting TikTok
        auth_url = self.body(self.client.post(CONNECT_URL))["authUrl"]

        # Then: TikTok gets its hex encoding of the verifier we kept
        query = parse_qs(urlparse(auth_url).query)
        session = OAuthSession.objects.get()
        self.assertTrue(auth_url.startswith("https://www.tiktok.com/v2/auth/authorize/"))
        self.assertEqual(query["client_key"], ["test-client-key"])
        self.assertEqual(query["code_challenge"], [Pkce(session.code_verifier).hex_challenge()])

    def test_a_completed_consent_connects_the_account(self):
        # Given: a connection was started and TikTok issues tokens
        self.sign_in()
        auth_url = self.body(self.client.post(CONNECT_URL))["authUrl"]
        state = parse_qs(urlparse(auth_url).query)["state"][0]
        self.given_answers(FakeAnswer(200, TOKEN), FakeAnswer(200, USER))

        # When: TikTok redirects back
        response = self.client.get(CALLBACK_URL, {"state": state, "code": "the-code"})

        # Then: the account is stored under its open_id, with the tokens encrypted at rest
        self.assertIn("result=connected", response["Location"])
        account = self.only_account()
        self.assertEqual((account.platform, account.external_id), ("tiktok", "open-id-1"))
        self.assertEqual(account.refresh_token, "rft.token")


class CreatorInfoScenarios(SocialTestCase):
    def setUp(self):
        super().setUp()
        self.sign_in()
        self.account = self.given_account(self.user, "tiktok")

    def given_account(self, user, platform: str, **fields) -> SocialAccount:
        return SocialAccount.objects.create(
            user=user,
            platform=platform,
            external_id=f"{platform}-{user.pk}",
            access_token="act.token",
            refresh_token="rft.token",
            token_expires_at=timezone.now() + timezone.timedelta(hours=12),
            **fields,
        )

    def url(self, account: SocialAccount) -> str:
        return f"/api/social/accounts/{account.pk}/creator-info"

    def test_the_creator_info_is_served_without_tokens(self):
        # Given: TikTok answers the query
        self.given_answers(FakeAnswer(200, CREATOR))

        # When: the composer asks for it
        response = self.client.get(self.url(self.account))

        # Then: it gets what the panel needs, and no token
        info = self.body(response)["creatorInfo"]
        self.assertEqual(info["nickname"], "A Creator")
        self.assertEqual(info["privacyLevelOptions"], ["SELF_ONLY", "FOLLOWER_OF_CREATOR"])
        self.assertTrue(info["commentDisabled"])
        self.assertNotIn("act.token", response.content.decode())

    def test_the_answer_is_cached_so_tiktoks_limit_is_not_spent(self):
        self.given_answers(FakeAnswer(200, CREATOR))

        self.client.get(self.url(self.account))
        self.client.get(self.url(self.account))

        self.assertEqual(len(self.http.sent), 1)

    def test_another_persons_account_is_not_found(self):
        # Given: somebody else's TikTok account
        other = User.objects.create_user("other@example.com", "another-password-1")
        theirs = self.given_account(other, "tiktok")

        # When / Then: it answers as if it did not exist
        self.assertEqual(self.client.get(self.url(theirs)).status_code, 404)
        self.assertEqual(self.http.sent, [])

    def test_an_account_of_another_platform_is_not_found(self):
        youtube = self.given_account(self.user, "youtube")

        self.assertEqual(self.client.get(self.url(youtube)).status_code, 404)

    def test_an_account_needing_reconnection_says_so(self):
        SocialAccount.objects.filter(pk=self.account.pk).update(status=SocialAccount.Status.NEEDS_REAUTH)

        response = self.client.get(self.url(self.account))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.body(response)["message"], "account_needs_reauth")

    def test_a_tiktok_outage_is_not_a_reason_to_reconnect(self):
        self.given_answers(*[FakeAnswer(503, {})] * 5)

        response = self.client.get(self.url(self.account))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.body(response)["message"], "platform_unavailable")

    def test_signing_in_is_required(self):
        self.client.logout()

        self.assertEqual(self.client.get(self.url(self.account)).status_code, 401)

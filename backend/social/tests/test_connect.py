from urllib.parse import parse_qs, urlparse

from django.db import connection
from django.test import override_settings
from django.utils import timezone

from platforms.oauth import pkce
from social.models import OAuthSession
from social.tests.base import CONNECT_URL, SocialTestCase


class ConnectScenarios(SocialTestCase):
    def test_signed_in_person_gets_a_consent_url(self):
        # Given: somebody is signed in
        self.sign_in()

        # When: they start connecting YouTube
        response = self.client.post(CONNECT_URL)

        # Then: they get a Google consent URL built from our client and redirect
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlparse(self.body(response)["authUrl"]).query)
        self.assertEqual(query["client_id"], ["test-client-id"])
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(
            query["redirect_uri"], ["http://testserver/api/social/youtube/callback"]
        )
        self.assertEqual(query["code_challenge_method"], ["S256"])

    def test_offline_access_is_requested(self):
        # Google issues a refresh token only with both of these, and without one
        # the connection would die after an hour.
        self.sign_in()

        query = parse_qs(urlparse(self.body(self.client.post(CONNECT_URL))["authUrl"]).query)

        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["prompt"], ["consent"])

    def test_both_upload_and_manage_scopes_are_requested(self):
        self.sign_in()

        query = parse_qs(urlparse(self.body(self.client.post(CONNECT_URL))["authUrl"]).query)

        self.assertIn("https://www.googleapis.com/auth/youtube.upload", query["scope"][0])
        self.assertIn("https://www.googleapis.com/auth/youtube", query["scope"][0])

    def test_the_verifier_stays_on_the_server(self):
        # Given: a connection is started
        self.sign_in()

        response = self.client.post(CONNECT_URL)

        # Then: the browser receives the challenge, never the verifier
        session = OAuthSession.objects.get()
        self.assertTrue(session.code_verifier)
        self.assertNotIn(session.code_verifier, response.content.decode())

    def test_the_challenge_is_derived_from_the_stored_verifier(self):
        # Given: a connection is started
        self.sign_in()

        # When: the consent URL is built
        query = parse_qs(urlparse(self.body(self.client.post(CONNECT_URL))["authUrl"]).query)

        # Then: the challenge is the provider's encoding of the verifier we kept
        session = OAuthSession.objects.get()
        self.assertEqual(query["code_challenge"], [pkce.s256_challenge(session.code_verifier)])

    def test_the_verifier_is_encrypted_at_rest(self):
        self.sign_in()
        self.client.post(CONNECT_URL)

        session = OAuthSession.objects.get()
        stored = self._raw_column("code_verifier", session.pk)

        self.assertNotEqual(stored, session.code_verifier)
        self.assertNotIn(session.code_verifier, stored)

    def test_the_session_belongs_to_the_person_who_started_it(self):
        self.sign_in()

        self.client.post(CONNECT_URL)

        self.assertEqual(OAuthSession.objects.get().user, self.user)

    def test_signing_in_is_required(self):
        response = self.client.post(CONNECT_URL)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(OAuthSession.objects.exists())

    def test_an_unknown_platform_is_not_found(self):
        self.sign_in()

        response = self.client.post("/api/social/myspace/connect")

        self.assertEqual(response.status_code, 404)

    def test_get_is_not_allowed(self):
        self.sign_in()

        response = self.client.get(CONNECT_URL)

        self.assertEqual(response.status_code, 405)

    @override_settings(RATE_LIMITS={"connect": (2, 60)})
    def test_repeated_attempts_are_rate_limited(self):
        self.sign_in()

        self.client.post(CONNECT_URL)
        self.client.post(CONNECT_URL)
        third = self.client.post(CONNECT_URL)

        self.assertEqual(third.status_code, 429)

    def test_expired_sessions_are_swept_when_a_new_one_starts(self):
        # Given: a session that is older than its time to live
        self.sign_in()
        self.client.post(CONNECT_URL)
        stale = OAuthSession.objects.get()
        OAuthSession.objects.filter(pk=stale.pk).update(
            created_at=OAuthSession.expiry_cutoff() - timezone.timedelta(seconds=1)
        )

        # When: another connection starts
        self.client.post(CONNECT_URL)

        # Then: only the new one remains
        self.assertEqual(OAuthSession.objects.count(), 1)
        self.assertNotEqual(OAuthSession.objects.get().pk, stale.pk)

    def _raw_column(self, column: str, pk: int) -> str:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {column} FROM social_oauthsession WHERE id = %s", [pk])
            return cursor.fetchone()[0]


class ConfigurationScenarios(SocialTestCase):
    @override_settings(YOUTUBE_CLIENT_ID="")
    def test_missing_credentials_are_reported_rather_than_crashing(self):
        # Given: the deployment has no YouTube client configured
        self.sign_in()

        response = self.client.post(CONNECT_URL)

        # Then: the person is told, and no half-started session is left pending
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            OAuthSession.objects.get().status, OAuthSession.Status.ERROR
        )

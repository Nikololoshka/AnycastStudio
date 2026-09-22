"""Coming back from the platform, written as Given / When / Then.

The callback is the only endpoint a stranger can aim a browser at, so most of
these scenarios are about what it refuses.
"""

import logging

import requests
from django.db import connection
from django.utils import timezone

from accounts.models import User
from social.models import OAuthSession, SocialAccount
from social.tests.base import (
    ACCESS_TOKEN,
    CALLBACK_URL,
    CHANNEL_ID,
    CLIENT_SECRET,
    CODE,
    REFRESH_TOKEN,
    FakeResponse,
    SocialTestCase,
)


class CallbackScenarios(SocialTestCase):
    def test_a_granted_authorisation_becomes_a_connected_account(self):
        # Given: a connection was started
        self.sign_in()
        state = self.given_started_connection()

        # When: Google sends the browser back with a code
        response = self.callback(state=state, code=CODE)

        # Then: the account is stored against the person who started it
        self.assertEqual(response.status_code, 302)
        self.assertIn("result=connected", response.headers["Location"])
        account = self.only_account()
        self.assertEqual(account.user, self.user)
        self.assertEqual(account.external_id, CHANNEL_ID)
        self.assertEqual(account.display_name, "A Channel")
        self.assertEqual(account.status, SocialAccount.Status.ACTIVE)

    def test_the_verifier_is_sent_to_the_token_endpoint(self):
        # Given: a started connection, whose verifier only the server knows
        self.sign_in()
        state = self.given_started_connection()
        verifier = OAuthSession.objects.get().code_verifier

        # When: the callback exchanges the code
        self.callback(state=state, code=CODE)

        # Then: the exchange proved possession of the verifier
        token_call = self.http.call_args_list[0]
        self.assertEqual(token_call.kwargs["data"]["code_verifier"], verifier)
        self.assertEqual(token_call.kwargs["data"]["grant_type"], "authorization_code")

    def test_tokens_are_encrypted_at_rest(self):
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)

        with connection.cursor() as cursor:
            cursor.execute("SELECT access_token, refresh_token FROM social_socialaccount")
            stored_access, stored_refresh = cursor.fetchone()

        self.assertNotIn(ACCESS_TOKEN, stored_access)
        self.assertNotIn(REFRESH_TOKEN, stored_refresh)
        account = self.only_account()
        self.assertEqual(account.access_token, ACCESS_TOKEN)
        self.assertEqual(account.refresh_token, REFRESH_TOKEN)

    def test_the_expiry_is_recorded_so_the_token_can_be_refreshed(self):
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)

        account = self.only_account()

        self.assertIsNotNone(account.token_expires_at)
        self.assertGreater(account.token_expires_at, timezone.now())

    def test_reconnecting_the_same_channel_updates_it_instead_of_duplicating(self):
        # Given: the channel is already connected
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)
        first = self.only_account().pk

        # When: the same channel is connected again
        self.given_platform_responds()
        self.callback(state=self.given_started_connection(), code=CODE)

        # Then: there is still one account, the same row
        self.assertEqual(SocialAccount.objects.count(), 1)
        self.assertEqual(self.only_account().pk, first)

    def test_a_state_cannot_be_replayed(self):
        # Given: a callback that already succeeded
        self.sign_in()
        state = self.given_started_connection()
        self.callback(state=state, code=CODE)

        # When: the same state arrives a second time
        self.given_platform_responds()
        response = self.callback(state=state, code=CODE)

        # Then: it is refused, and nothing is written twice
        self.assertIn("result=invalid", response.headers["Location"])
        self.assertEqual(SocialAccount.objects.count(), 1)

    def test_a_state_from_another_person_is_refused(self):
        # Given: one person starts a connection
        self.sign_in()
        state = self.given_started_connection()

        # When: a different signed-in person follows that callback URL
        intruder = User.objects.create_user("intruder@example.com", "another-password-99")
        self.client.force_login(intruder)
        response = self.callback(state=state, code=CODE)

        # Then: nothing is connected. Otherwise an attacker could graft their own
        # channel onto somebody elses account.
        self.assertIn("result=invalid", response.headers["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_a_callback_with_no_session_cookie_is_refused(self):
        self.sign_in()
        state = self.given_started_connection()
        self.client.logout()

        response = self.callback(state=state, code=CODE)

        self.assertIn("result=invalid", response.headers["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_an_unknown_state_is_refused(self):
        self.sign_in()

        response = self.callback(state="never-issued", code=CODE)

        self.assertIn("result=invalid", response.headers["Location"])

    def test_a_missing_state_is_refused(self):
        self.sign_in()

        response = self.callback(code=CODE)

        self.assertIn("result=invalid", response.headers["Location"])

    def test_an_expired_session_is_refused(self):
        # Given: the person left the consent screen open too long
        self.sign_in()
        state = self.given_started_connection()
        OAuthSession.objects.update(
            created_at=OAuthSession.expiry_cutoff() - timezone.timedelta(seconds=1)
        )

        response = self.callback(state=state, code=CODE)

        self.assertIn("result=invalid", response.headers["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_the_person_cancelling_is_reported_as_cancelled(self):
        self.sign_in()
        state = self.given_started_connection()

        response = self.callback(state=state, error="access_denied")

        self.assertIn("result=cancelled", response.headers["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_a_callback_without_a_code_is_reported_as_cancelled(self):
        self.sign_in()
        state = self.given_started_connection()

        response = self.callback(state=state)

        self.assertIn("result=cancelled", response.headers["Location"])

    def test_a_rejected_exchange_is_reported_as_failed(self):
        self.sign_in()
        state = self.given_started_connection()
        self.http.side_effect = [FakeResponse(400, {"error": "invalid_grant"})]

        response = self.callback(state=state, code=CODE)

        self.assertIn("result=failed", response.headers["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_a_non_json_response_is_reported_as_failed(self):
        self.sign_in()
        state = self.given_started_connection()
        self.http.side_effect = [FakeResponse(200, None, text="<html>error</html>")]

        response = self.callback(state=state, code=CODE)

        self.assertIn("result=failed", response.headers["Location"])

    def test_a_google_account_without_a_channel_is_reported_as_failed(self):
        self.sign_in()
        state = self.given_started_connection()
        self.given_platform_responds(channel={"items": []})

        response = self.callback(state=state, code=CODE)

        self.assertIn("result=failed", response.headers["Location"])
        self.assertFalse(SocialAccount.objects.exists())

    def test_post_is_not_allowed(self):
        self.sign_in()

        response = self.client.post(CALLBACK_URL)

        self.assertEqual(response.status_code, 405)


class LeakScenarios(SocialTestCase):
    def test_no_secret_reaches_the_response_or_the_logs(self):
        # Given: a connection about to complete
        self.sign_in()
        state = self.given_started_connection()
        verifier = OAuthSession.objects.get().code_verifier

        # When: the callback runs with everything logged
        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger("social").debug("marker")  # assertLogs fails if nothing is logged
            response = self.callback(state=state, code=CODE)

        # Then: none of it appears anywhere a person or an operator could read
        haystack = response.content.decode() + response.headers["Location"] + "\n".join(logs.output)
        for secret in (CLIENT_SECRET, ACCESS_TOKEN, REFRESH_TOKEN, verifier, CODE):
            self.assertNotIn(secret, haystack)

    def test_a_network_failure_does_not_report_the_request_url(self):
        # The requests exception text contains the URL, and the token request
        # body carries client_secret, so only the exception class may be reported.
        self.sign_in()
        state = self.given_started_connection()
        self.http.side_effect = requests.ConnectionError(
            "failed to post https://oauth2.googleapis.com/token?secret=" + CLIENT_SECRET
        )

        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger("social").debug("marker")
            response = self.callback(state=state, code=CODE)

        self.assertIn("result=failed", response.headers["Location"])
        self.assertNotIn(CLIENT_SECRET, "\n".join(logs.output))

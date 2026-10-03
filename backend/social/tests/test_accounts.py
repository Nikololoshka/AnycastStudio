from unittest import mock

from django.db import connections
from django.utils import timezone

from accounts.models import User
from media.models import MediaAsset
import aiohttp

from platforms.core import PlatformError
from platforms.tests.fakes.http import FakeAnswer
from publishing.models import Publication, PublicationTarget
from social.models import SocialAccount
from social.tests.base import (
    ACCESS_TOKEN,
    ACCOUNTS_URL,
    CODE,
    REFRESH_TOKEN,
    
    SocialTestCase,
)

NEW_ACCESS_TOKEN = "ya29.refreshed-access-token"
# A valid Fernet key that nothing was ever written with.
OTHER_KEY = "v2:8Ys98H3X6AXd66tWzmiUh4TkcxGc9qX_C3EBkfKYOgg="


class AccountListScenarios(SocialTestCase):
    def test_a_connected_account_is_listed(self):
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)

        body = self.body(self.client.get(ACCOUNTS_URL))

        self.assertEqual(len(body["accounts"]), 1)
        self.assertEqual(body["accounts"][0]["platform"], "youtube")
        self.assertEqual(body["accounts"][0]["displayName"], "A Channel")

    def test_no_token_is_ever_sent_to_the_browser(self):
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)

        content = self.client.get(ACCOUNTS_URL).content.decode()

        self.assertNotIn(ACCESS_TOKEN, content)
        self.assertNotIn(REFRESH_TOKEN, content)
        self.assertNotIn("accessToken", content)
        self.assertNotIn("refreshToken", content)

    def test_the_connectable_platforms_are_reported(self):
        self.sign_in()

        body = self.body(self.client.get(ACCOUNTS_URL))

        self.assertEqual(body["platforms"], ["instagram", "tiktok", "x", "youtube"])

    def test_another_persons_accounts_are_not_listed(self):
        # Given: somebody else has connected a channel
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)

        # When: a different person asks for their accounts
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        # Then: they see none of it
        self.assertEqual(self.body(self.client.get(ACCOUNTS_URL))["accounts"], [])

    def test_signing_in_is_required(self):
        self.assertEqual(self.client.get(ACCOUNTS_URL).status_code, 401)


class DisconnectScenarios(SocialTestCase):
    def connect(self) -> SocialAccount:
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)
        return self.only_account()

    def assert_disconnected(self, account: SocialAccount):
        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.REVOKED)
        self.assertEqual(account.access_token, "")
        self.assertEqual(account.refresh_token, "")

    def test_disconnecting_forgets_the_tokens(self):
        account = self.connect()
        self.given_answers(FakeAnswer(200, {}))

        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        self.assertEqual(response.status_code, 200)
        self.assert_disconnected(account)

    def test_a_disconnected_account_is_no_longer_listed(self):
        account = self.connect()
        self.given_answers(FakeAnswer(200, {}))
        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        body = self.body(self.client.get(ACCOUNTS_URL))

        self.assertEqual(body["accounts"], [])
        self.assertEqual(self.client.delete(f"{ACCOUNTS_URL}/{account.pk}").status_code, 404)

    def test_an_account_that_has_published_can_be_disconnected(self):
        # Given: an account with a publication, which keeps the row in the history
        account = self.connect()
        asset = MediaAsset.objects.create(
            user=self.user, filename="clip.mp4", mime_type="video/mp4", size_bytes=1, storage_path="clip.mp4"
        )
        publication = Publication.objects.create(user=self.user, asset=asset, title="A clip")
        PublicationTarget.objects.create(publication=publication, platform="youtube", social_account=account)
        self.given_answers(FakeAnswer(200, {}))

        # When: the person disconnects it
        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        # Then: it answers, and the tokens are gone while the history stays
        self.assertEqual(response.status_code, 200)
        self.assert_disconnected(account)
        self.assertTrue(PublicationTarget.objects.filter(social_account=account).exists())

    def test_reconnecting_a_disconnected_channel_brings_it_back(self):
        account = self.connect()
        self.given_answers(FakeAnswer(200, {}))
        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        self.given_platform_responds()
        self.callback(state=self.given_started_connection(), code=CODE)

        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.ACTIVE)
        self.assertEqual(account.access_token, ACCESS_TOKEN)

    def test_revoking_is_tried_once(self):
        account = self.connect()
        self.http.forget()
        self.given_answers(*[FakeAnswer(503, {})] * 3)

        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        self.assertEqual(len(self.http.sent), 1)
        self.assert_disconnected(account)

    def test_disconnecting_asks_the_platform_to_revoke(self):
        account = self.connect()
        self.given_answers(FakeAnswer(200, {}))

        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        revoke_call = self.http.sent[-1]
        self.assertIn("revoke", revoke_call.url)
        self.assertEqual(revoke_call.data, {"token": REFRESH_TOKEN})

    def test_an_account_without_a_refresh_token_is_still_revoked(self):
        # Given: a connected account that holds only an access token
        account = self.connect()
        SocialAccount.objects.filter(pk=account.pk).update(refresh_token="")
        self.given_answers(FakeAnswer(200, {}))

        # When: the person disconnects it
        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        # Then: the platform is asked to revoke the access token
        revoke_call = self.http.sent[-1]
        self.assertIn("revoke", revoke_call.url)
        self.assertEqual(revoke_call.data, {"token": ACCESS_TOKEN})
        self.assert_disconnected(account)

    def test_an_account_without_tokens_is_not_revoked(self):
        # Given: an account whose tokens are already gone
        account = self.connect()
        SocialAccount.objects.filter(pk=account.pk).update(access_token="", refresh_token="")
        self.http.forget()

        # When: the person disconnects it
        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        # Then: nothing is sent to the platform
        self.assertEqual(self.http.sent, [])
        self.assert_disconnected(account)

    def test_the_account_goes_even_if_the_platform_refuses_to_revoke(self):
        # Given: revoking fails, which is Google's business, not the person's
        account = self.connect()
        self.given_answers(aiohttp.ClientConnectionError("Cannot connect"))

        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        self.assertEqual(response.status_code, 200)
        self.assert_disconnected(account)

    def test_another_persons_account_is_not_found(self):
        # Given: somebody else's connected account
        account = self.connect()
        other = User.objects.create_user("other@example.com", "another-password-99")
        self.client.force_login(other)

        # When: they try to disconnect it by id
        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        # Then: 404, not 403 — the id of a row they cannot see tells them nothing
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SocialAccount.objects.filter(pk=account.pk).exists())

    def test_get_is_not_allowed_on_a_single_account(self):
        account = self.connect()

        self.assertEqual(self.client.get(f"{ACCOUNTS_URL}/{account.pk}").status_code, 405)


class TokenRefreshScenarios(SocialTestCase):
    def given_connected_account(self, **overrides) -> SocialAccount:
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)
        account = self.only_account()
        if overrides:
            SocialAccount.objects.filter(pk=account.pk).update(**overrides)
            account.refresh_from_db()
        return account

    def test_a_token_that_is_still_good_is_used_as_is(self):
        account = self.given_connected_account()
        self.http.forget()

        token = self.valid_token(account.pk)

        self.assertEqual(token, ACCESS_TOKEN)
        self.assertEqual(self.http.sent, [])

    def test_a_token_near_expiry_is_refreshed_before_it_is_used(self):
        # Given: the token expires inside the refresh margin
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.given_answers(
            FakeAnswer(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})
        )

        token = self.valid_token(account.pk)

        self.assertEqual(token, NEW_ACCESS_TOKEN)

    def test_the_refresh_token_survives_a_refresh_that_omits_it(self):
        # Google does not return the refresh token when refreshing. Dropping it
        # would turn a long-lived connection into a one-hour one.
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.given_answers(
            FakeAnswer(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})
        )

        self.valid_token(account.pk)

        account.refresh_from_db()
        self.assertEqual(account.refresh_token, REFRESH_TOKEN)

    def test_a_rotated_refresh_token_replaces_the_stored_one(self):
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.given_answers(
            FakeAnswer(
                200,
                {
                    "access_token": NEW_ACCESS_TOKEN,
                    "refresh_token": "1//rotated-refresh-token",
                    "expires_in": 3600,
                },
            )
        )

        self.valid_token(account.pk)

        account.refresh_from_db()
        self.assertEqual(account.refresh_token, "1//rotated-refresh-token")

    def test_a_refused_refresh_marks_the_account_for_reconnection(self):
        # Given: the person revoked our access in their Google settings
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.given_answers(FakeAnswer(400, {"error": "invalid_grant"}))

        with self.assertRaises(PlatformError):
            self.valid_token(account.pk)

        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.NEEDS_REAUTH)
        self.assertTrue(account.last_error)

    def test_an_account_without_a_refresh_token_asks_to_be_reconnected(self):
        account = self.given_connected_account(token_expires_at=timezone.now(), refresh_token="")

        with self.assertRaises(PlatformError):
            self.valid_token(account.pk)

        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.NEEDS_REAUTH)

    def test_needing_reconnection_is_reported_to_the_browser(self):
        account = self.given_connected_account(status=SocialAccount.Status.NEEDS_REAUTH)

        body = self.body(self.client.get(ACCOUNTS_URL))

        self.assertTrue(body["accounts"][0]["needsReauth"])
        self.assertEqual(account.pk, body["accounts"][0]["id"])

    def test_the_second_caller_of_a_concurrent_refresh_does_not_refresh_again(self):
        # Given: an expiring token, refreshed by whoever gets the row lock first
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.given_answers(
            FakeAnswer(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})
        )
        self.valid_token(account.pk)
        self.http.forget()

        # When: a second caller arrives holding the stale copy of the row
        token = self.valid_token(account.pk)

        # Then: it sees the fresh token and does not call Google again. On a
        # platform that rotates refresh tokens, a second call would burn one.
        self.assertEqual(token, NEW_ACCESS_TOKEN)
        self.assertEqual(self.http.sent, [])


    def test_a_forced_refresh_asks_google_even_when_the_token_looks_good(self):
        # Given: a token our clock thinks is valid for another hour, which Google has refused
        account = self.given_connected_account(token_expires_at=timezone.now() + timezone.timedelta(hours=1))
        self.http.forget()
        self.given_answers(FakeAnswer(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600}))

        # When: the upload asks for a fresh one
        token = self.refreshed_token(account.pk)

        # Then: Google was asked, and the new token is stored
        self.assertEqual(token, NEW_ACCESS_TOKEN)
        self.assertEqual(len(self.http.sent), 1)

    def test_the_refresh_does_not_hold_a_transaction_open(self):
        # Given: an expiring token, and a way to see the transaction depth during the call
        account = self.given_connected_account(token_expires_at=timezone.now())
        database = connections["default"]
        depth_outside = len(database.atomic_blocks)
        depth_during_call = []

        def google():
            depth_during_call.append(len(database.atomic_blocks))
            return FakeAnswer(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})

        self.given_answers(google)

        # When: the token is refreshed
        self.valid_token(account.pk)

        # Then: Google was called outside any transaction of ours
        self.assertEqual(depth_during_call, [depth_outside])

    def test_a_google_outage_does_not_ask_for_reconnection(self):
        # Given: Google keeps answering 503
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.given_answers(*[FakeAnswer(503, {})] * 3)

        # When: the refresh gives up
        with self.assertRaises(PlatformError):
            self.valid_token(account.pk)

        # Then: the account stays active, because nothing was refused
        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.ACTIVE)

    def test_the_periodic_task_refreshes_what_expires_within_the_hour(self):
        # Given: a token that is still valid for forty minutes
        account = self.given_connected_account(token_expires_at=timezone.now() + timezone.timedelta(minutes=40))
        self.given_answers(FakeAnswer(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600}))

        # When: the periodic task runs
        refreshed = self.refresh_expiring()

        # Then: it refreshed it ahead of time, and says so
        self.assertEqual(refreshed, 1)
        account.refresh_from_db()
        self.assertEqual(account.access_token, NEW_ACCESS_TOKEN)


class EncryptionScenarios(SocialTestCase):
    def test_a_token_written_with_a_retired_key_reads_back_empty(self):
        # Given: an account stored under a key that is no longer configured
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)
        account = self.only_account()

        # When: every key is replaced
        from common.encryption import keys

        with mock.patch.object(
            keys.settings, "TOKEN_ENCRYPTION_KEYS", [OTHER_KEY], create=True
        ):
            keys.reset_cipher_cache()
            try:
                with self.assertLogs("common.encryption.fields", level="WARNING") as logs:
                    account.refresh_from_db()
                unreadable = account.access_token
            finally:
                keys.reset_cipher_cache()

        # Then: it reads as missing rather than crashing, so the person is asked
        # to reconnect instead of meeting a 500
        self.assertEqual(unreadable, "")
        # And: the log names the field but never the stored value
        output = "\n".join(logs.output)
        self.assertIn("SocialAccount.access_token", output)
        self.assertNotIn(ACCESS_TOKEN, output)
        self.assertNotIn(REFRESH_TOKEN, output)

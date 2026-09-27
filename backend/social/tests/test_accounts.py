"""Listing, disconnecting and keeping tokens usable, as Given / When / Then."""

from unittest import mock

from django.utils import timezone

from accounts.models import User
from platforms.oauth import ProviderError
from social import services
from social.models import SocialAccount
from social.tests.base import (
    ACCESS_TOKEN,
    ACCOUNTS_URL,
    CODE,
    REFRESH_TOKEN,
    FakeResponse,
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

        self.assertEqual(body["platforms"], ["youtube"])

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

    def test_disconnecting_removes_the_account_and_its_tokens(self):
        account = self.connect()
        self.http.side_effect = [FakeResponse(200, {})]

        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SocialAccount.objects.exists())

    def test_disconnecting_asks_the_platform_to_revoke(self):
        account = self.connect()
        self.http.side_effect = [FakeResponse(200, {})]

        self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        revoke_call = self.http.call_args_list[-1]
        self.assertIn("revoke", revoke_call.args[1])

    def test_the_account_goes_even_if_the_platform_refuses_to_revoke(self):
        # Given: revoking fails, which is Google's business, not the person's
        account = self.connect()
        self.http.side_effect = ProviderError("Google request failed: ConnectionError")

        response = self.client.delete(f"{ACCOUNTS_URL}/{account.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SocialAccount.objects.exists())

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
        self.http.reset_mock(side_effect=True)

        token = services.get_valid_access_token(account)

        self.assertEqual(token, ACCESS_TOKEN)
        self.http.assert_not_called()

    def test_a_token_near_expiry_is_refreshed_before_it_is_used(self):
        # Given: the token expires inside the refresh margin
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.http.side_effect = [
            FakeResponse(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})
        ]

        token = services.get_valid_access_token(account)

        self.assertEqual(token, NEW_ACCESS_TOKEN)

    def test_the_refresh_token_survives_a_refresh_that_omits_it(self):
        # Google does not return the refresh token when refreshing. Dropping it
        # would turn a long-lived connection into a one-hour one.
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.http.side_effect = [
            FakeResponse(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})
        ]

        services.get_valid_access_token(account)

        account.refresh_from_db()
        self.assertEqual(account.refresh_token, REFRESH_TOKEN)

    def test_a_rotated_refresh_token_replaces_the_stored_one(self):
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.http.side_effect = [
            FakeResponse(
                200,
                {
                    "access_token": NEW_ACCESS_TOKEN,
                    "refresh_token": "1//rotated-refresh-token",
                    "expires_in": 3600,
                },
            )
        ]

        services.get_valid_access_token(account)

        account.refresh_from_db()
        self.assertEqual(account.refresh_token, "1//rotated-refresh-token")

    def test_a_refused_refresh_marks_the_account_for_reconnection(self):
        # Given: the person revoked our access in their Google settings
        account = self.given_connected_account(token_expires_at=timezone.now())
        self.http.side_effect = [FakeResponse(400, {"error": "invalid_grant"})]

        with self.assertRaises(ProviderError):
            services.get_valid_access_token(account)

        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.NEEDS_REAUTH)
        self.assertTrue(account.last_error)

    def test_an_account_without_a_refresh_token_asks_to_be_reconnected(self):
        account = self.given_connected_account(token_expires_at=timezone.now(), refresh_token="")

        with self.assertRaises(ProviderError):
            services.get_valid_access_token(account)

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
        self.http.side_effect = [
            FakeResponse(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})
        ]
        services.get_valid_access_token(account)
        self.http.reset_mock(side_effect=True)

        # When: a second caller arrives holding the stale copy of the row
        token = services.get_valid_access_token(account)

        # Then: it sees the fresh token and does not call Google again. On a
        # platform that rotates refresh tokens, a second call would burn one.
        self.assertEqual(token, NEW_ACCESS_TOKEN)
        self.http.assert_not_called()


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

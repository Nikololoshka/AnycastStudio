from unittest import mock

from django.utils import timezone

from config.wiring import container
from platforms.core.auth.token_service import TokenService
from platforms.core.errors import ProviderError
from social.models import SocialAccount
from social.tests.base import CODE, FakeResponse, SocialTestCase

NEW_ACCESS_TOKEN = "ya29.refreshed-access-token"
OTHER_ACCESS_TOKEN = "ya29.refreshed-by-the-other-caller"


class RefreshLeaseScenarios(SocialTestCase):
    def setUp(self):
        super().setUp()
        sleeper = mock.patch("platforms.core.ports.clock.time.sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def given_expiring_account(self, **overrides) -> SocialAccount:
        self.sign_in()
        self.callback(state=self.given_started_connection(), code=CODE)
        account = self.only_account()
        SocialAccount.objects.filter(pk=account.pk).update(token_expires_at=timezone.now(), **overrides)
        account.refresh_from_db()
        self.http.reset_mock(side_effect=True)
        return account

    def given_another_caller_is_refreshing(self, account: SocialAccount) -> None:
        SocialAccount.objects.filter(pk=account.pk).update(refresh_lease_until=timezone.now() + TokenService.REFRESH_LEASE)

    def other_caller_finishes(self, account: SocialAccount):
        def finish(_seconds):
            SocialAccount.objects.filter(pk=account.pk).update(
                access_token=OTHER_ACCESS_TOKEN,
                token_expires_at=timezone.now() + timezone.timedelta(hours=1),
                refresh_lease_until=None,
            )

        return finish

    def test_a_caller_waits_for_the_refresh_already_in_progress(self):
        # Given: another caller holds the lease and finishes while we wait
        account = self.given_expiring_account()
        self.given_another_caller_is_refreshing(account)
        self.sleep.side_effect = self.other_caller_finishes(account)

        # When: we need a valid token
        token = container().token_service.valid(account.pk)

        # Then: we get theirs without spending the rotating refresh token again
        self.assertEqual(token, OTHER_ACCESS_TOKEN)
        self.http.assert_not_called()

    def test_a_refresh_that_never_finishes_elsewhere_is_reported_as_transient(self):
        # Given: another caller holds the lease and never finishes
        account = self.given_expiring_account()
        self.given_another_caller_is_refreshing(account)

        # When: we need a valid token
        with self.assertRaises(ProviderError) as raised:
            container().token_service.valid(account.pk)

        # Then: the failure is transient, the account stays usable, the platform was not called
        self.assertTrue(raised.exception.transient)
        account.refresh_from_db()
        self.assertEqual(account.status, SocialAccount.Status.ACTIVE)
        self.http.assert_not_called()

    def test_a_lease_left_by_a_dead_worker_does_not_block_the_refresh(self):
        # Given: a lease that ran out without being released
        account = self.given_expiring_account(refresh_lease_until=timezone.now() - timezone.timedelta(seconds=1))
        self.http.side_effect = [FakeResponse(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})]

        # When: we need a valid token
        token = container().token_service.valid(account.pk)

        # Then: we refresh it ourselves
        self.assertEqual(token, NEW_ACCESS_TOKEN)

    def test_the_lease_is_released_after_a_refresh(self):
        # Given: an expiring token
        account = self.given_expiring_account()
        self.http.side_effect = [FakeResponse(200, {"access_token": NEW_ACCESS_TOKEN, "expires_in": 3600})]

        # When: it is refreshed
        container().token_service.valid(account.pk)

        # Then: nobody else has to wait
        account.refresh_from_db()
        self.assertIsNone(account.refresh_lease_until)

    def test_the_lease_is_released_after_a_refused_refresh(self):
        # Given: the platform refuses the refresh token
        account = self.given_expiring_account()
        self.http.side_effect = [FakeResponse(400, {"error": "invalid_grant"})]

        # When: the refresh fails
        with self.assertRaises(ProviderError):
            container().token_service.valid(account.pk)

        # Then: the lease is gone and the account asks to be reconnected
        account.refresh_from_db()
        self.assertIsNone(account.refresh_lease_until)
        self.assertEqual(account.status, SocialAccount.Status.NEEDS_REAUTH)

    def test_a_waiting_caller_learns_that_the_other_refresh_was_refused(self):
        # Given: the other caller's refresh ends with the account needing reconnection
        account = self.given_expiring_account()
        self.given_another_caller_is_refreshing(account)
        self.sleep.side_effect = lambda _seconds: SocialAccount.objects.filter(pk=account.pk).update(
            status=SocialAccount.Status.NEEDS_REAUTH, refresh_lease_until=None
        )

        # When: we need a valid token
        with self.assertRaises(ProviderError) as raised:
            container().token_service.valid(account.pk)

        # Then: we are told to reconnect, not to try again
        self.assertFalse(raised.exception.transient)
        self.http.assert_not_called()

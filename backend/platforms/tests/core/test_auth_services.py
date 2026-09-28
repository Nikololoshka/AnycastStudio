from datetime import timedelta

from django.test import SimpleTestCase

from platforms.core.auth.account import AccountStatus, AccountTokens
from platforms.core.auth.account_service import AccountService
from platforms.core.auth.connect_flow import ConnectFlow
from platforms.core.auth.session import ConnectOutcome, OAuthSessionStatus
from platforms.core.auth.token_service import TokenService
from platforms.core.errors import NotFound, ProviderError

from ..fakes.auth import FakeAccounts, FakeProvider, FakeSessions
from ..fakes.clock import FakeClock
from ..fakes.publishing import FakePublisher, FakeValidator, fake_catalog

SESSION_TTL = timedelta(minutes=10)


class AuthScenarioBase(SimpleTestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.accounts = FakeAccounts()
        self.provider = FakeProvider()
        catalog = fake_catalog(FakePublisher(), FakeValidator(), provider=self.provider)
        self.tokens = TokenService(self.accounts, catalog, self.clock)
        self.account_service = AccountService(self.accounts, catalog, self.clock)
        self.sessions = FakeSessions(self.clock)
        self.flow = ConnectFlow(self.sessions, self.account_service, catalog, self.clock, SESSION_TTL)

    def given_account(self, expires_in: timedelta = timedelta(hours=1), **fields) -> AccountTokens:
        values = {
            "id": 7,
            "platform": "fake",
            "status": AccountStatus.ACTIVE,
            "access_token": "stored",
            "refresh_token": "refresh-1",
            "expires_at": self.clock.now() + expires_in,
        }
        return self.accounts.given_tokens(AccountTokens(**{**values, **fields}))


class TokenServiceScenarios(AuthScenarioBase):
    def test_a_token_that_is_still_good_is_used_as_is(self):
        self.given_account()

        self.assertEqual(self.tokens.valid(7), "stored")
        self.assertEqual(self.provider.refreshes, [])

    def test_a_token_inside_the_margin_is_refreshed_first(self):
        self.given_account(expires_in=TokenService.REFRESH_MARGIN / 2)

        self.assertEqual(self.tokens.valid(7), "fresh")
        self.assertEqual(self.provider.refreshes, ["refresh-1"])

    def test_the_refresh_token_survives_a_refresh_that_omits_it(self):
        self.given_account(expires_in=timedelta(0))

        self.tokens.valid(7)

        self.assertEqual(self.accounts.tokens_of(7).refresh_token, "refresh-1")

    def test_a_refused_refresh_asks_for_reconnection(self):
        self.given_account(expires_in=timedelta(0))
        self.provider.refresh_answer = ProviderError("invalid_grant")

        with self.assertRaises(ProviderError) as raised:
            self.tokens.valid(7)

        self.assertFalse(raised.exception.transient)
        self.assertEqual(self.accounts.tokens_of(7).status, AccountStatus.NEEDS_REAUTH)
        self.assertIsNone(self.accounts.tokens_of(7).lease_until)

    def test_an_outage_keeps_the_account_usable(self):
        self.given_account(expires_in=timedelta(0))
        self.provider.refresh_answer = ProviderError("unavailable", transient=True)

        with self.assertRaises(ProviderError) as raised:
            self.tokens.valid(7)

        self.assertTrue(raised.exception.transient)
        self.assertEqual(self.accounts.tokens_of(7).status, AccountStatus.ACTIVE)

    def test_an_account_without_a_refresh_token_asks_for_reconnection(self):
        self.given_account(expires_in=timedelta(0), refresh_token="")

        with self.assertRaises(ProviderError):
            self.tokens.valid(7)

        self.assertEqual(self.accounts.reasons[7], "No refresh token stored")

    def test_a_caller_waits_for_the_refresh_already_in_progress(self):
        # Given: another caller holds the lease and finishes while we wait
        account = self.given_account(expires_in=timedelta(0), lease_until=self.clock.now() + timedelta(minutes=1))
        later = account.expires_at + timedelta(hours=1)
        self.clock.on_sleep = lambda: self.accounts._update(7, access_token="theirs", expires_at=later, lease_until=None)

        # When / Then: we take their token without spending the refresh token
        self.assertEqual(self.tokens.valid(7), "theirs")
        self.assertEqual(self.provider.refreshes, [])

    def test_a_refresh_that_never_finishes_elsewhere_is_transient(self):
        self.given_account(expires_in=timedelta(0), lease_until=self.clock.now() + timedelta(hours=1))

        with self.assertRaises(ProviderError) as raised:
            self.tokens.valid(7)

        self.assertTrue(raised.exception.transient)

    def test_the_periodic_refresh_counts_what_it_renewed(self):
        self.given_account(expires_in=timedelta(minutes=40))

        self.assertEqual(self.tokens.refresh_expiring(), 1)
        self.assertEqual(self.accounts.tokens_of(7).access_token, "fresh")


class AccountServiceScenarios(AuthScenarioBase):
    def test_disconnecting_revokes_at_the_platform_and_forgets_the_tokens(self):
        self.given_account()

        self.account_service.disconnect(7)

        self.assertEqual(self.provider.revoked, [("stored", "refresh-1")])
        tokens = self.accounts.tokens_of(7)
        self.assertEqual((tokens.access_token, tokens.refresh_token, tokens.status), ("", "", AccountStatus.REVOKED))

    def test_a_failed_revoke_still_disconnects(self):
        self.given_account()
        self.provider.revoke_failure = ProviderError("down")

        self.account_service.disconnect(7)

        self.assertEqual(self.accounts.tokens_of(7).status, AccountStatus.REVOKED)


class ConnectFlowScenarios(AuthScenarioBase):
    def started(self, owner_id: int = 1) -> str:
        self.flow.start(owner_id, "fake")
        return self.sessions.only()["state"]

    def test_an_unknown_platform_is_not_found(self):
        with self.assertRaises(NotFound):
            self.flow.start(1, "myspace")

    def test_the_consent_url_carries_the_state_and_a_challenge(self):
        url = self.flow.start(1, "fake")

        row = self.sessions.only()
        self.assertIn(f"state={row['state']}", url)
        self.assertIn("code_challenge=", url)
        self.assertTrue(row["verifier"])

    def test_the_owner_completing_the_consent_connects_the_account(self):
        state = self.started()

        outcome = self.flow.complete("fake", state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.CONNECTED)
        self.assertEqual(self.accounts.saved[0][:2], (1, "fake"))
        self.assertEqual(self.sessions.only()["status"], OAuthSessionStatus.DONE)

    def test_a_state_opened_by_somebody_else_is_refused(self):
        state = self.started(owner_id=1)

        outcome = self.flow.complete("fake", state, "the-code", refused=False, requester_id=2)

        self.assertEqual(outcome, ConnectOutcome.INVALID)
        self.assertEqual(self.accounts.saved, [])
        self.assertEqual(self.sessions.only()["status"], OAuthSessionStatus.ERROR)

    def test_a_state_is_used_once(self):
        state = self.started()
        self.flow.complete("fake", state, "the-code", refused=False, requester_id=1)

        again = self.flow.complete("fake", state, "the-code", refused=False, requester_id=1)

        self.assertEqual(again, ConnectOutcome.INVALID)
        self.assertEqual(len(self.accounts.saved), 1)

    def test_an_expired_state_is_refused(self):
        state = self.started()
        self.clock.advance(SESSION_TTL + timedelta(seconds=1))

        outcome = self.flow.complete("fake", state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.INVALID)

    def test_a_declined_consent_is_cancelled(self):
        state = self.started()

        outcome = self.flow.complete("fake", state, None, refused=True, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.CANCELLED)

    def test_a_refused_exchange_fails_without_saving(self):
        state = self.started()
        self.provider.exchange_answer = ProviderError("invalid_grant")

        outcome = self.flow.complete("fake", state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.FAILED)
        self.assertEqual(self.accounts.saved, [])

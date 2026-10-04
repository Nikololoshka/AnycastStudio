from datetime import timedelta
from unittest import IsolatedAsyncioTestCase

from platforms.core import AuthToken, PlatformError, PlatformFailure
from platforms.tests.fakes.platform import FAKE, FakePlatform, FakeRegistry
from services.core.accounts import AccountStatus, AccountTokens, ConnectOutcome, OAuthSessionStatus
from services.core.domain import NotFound, Unavailable
from services.usecases.accounts import AccountService, ConnectFlow, TokenService

from .fakes.accounts import FakeAccounts, FakeSessions
from .fakes.clock import FakeClock

SESSION_TTL = timedelta(minutes=10)


class AccountScenarioBase(IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.accounts = FakeAccounts()
        self.platform = FakePlatform()
        self.authorization = self.platform.authorization
        registry = FakeRegistry(self.platform)
        self.tokens = TokenService(self.accounts, registry, self.clock)
        self.account_service = AccountService(self.accounts, registry, self.clock)
        self.sessions = FakeSessions(self.clock)
        self.flow = ConnectFlow(self.sessions, self.account_service, registry, self.clock, SESSION_TTL)

    def given_account(self, expires_in: timedelta = timedelta(hours=1), **fields) -> AccountTokens:
        values = {
            "id": 7,
            "platform": FAKE,
            "status": AccountStatus.ACTIVE,
            "access_token": "stored",
            "refresh_token": "refresh-1",
            "expires_at": self.clock.now() + expires_in,
        }
        return self.accounts.given_tokens(AccountTokens(**{**values, **fields}))


class TokenServiceScenarios(AccountScenarioBase):
    async def test_a_token_that_is_still_good_is_used_as_is(self):
        self.given_account()

        self.assertEqual(await self.tokens.valid(7), "stored")
        self.assertEqual(self.authorization.refreshes, [])

    async def test_a_token_inside_the_margin_is_refreshed_first(self):
        self.given_account(expires_in=TokenService.REFRESH_MARGIN / 2)

        self.assertEqual(await self.tokens.valid(7), "fresh")
        self.assertEqual(self.authorization.refreshes, ["refresh-1"])

    async def test_the_refresh_token_survives_a_refresh_that_omits_it(self):
        self.given_account(expires_in=timedelta(0))

        await self.tokens.valid(7)

        self.assertEqual((await self.accounts.get_account_tokens(7)).refresh_token, "refresh-1")

    async def test_a_revoked_grant_asks_for_reconnection(self):
        # Given: the platform says the refresh token is no longer valid
        self.given_account(expires_in=timedelta(0))
        self.authorization.refresh_answer = PlatformError(PlatformFailure.GRANT_REVOKED, "invalid_grant")

        # When / Then: the account must be reconnected, and the lease is released
        with self.assertRaises(PlatformError) as raised:
            await self.tokens.valid(7)
        self.assertEqual(raised.exception.failure, PlatformFailure.GRANT_REVOKED)
        account = await self.accounts.get_account_tokens(7)
        self.assertEqual(account.status, AccountStatus.NEEDS_REAUTH)
        self.assertIsNone(account.lease_until)
        self.assertEqual(self.accounts.reasons[7], "invalid_grant")

    async def test_a_missing_scope_asks_for_reconnection(self):
        self.given_account(expires_in=timedelta(0))
        self.authorization.refresh_answer = PlatformError(PlatformFailure.SCOPE_MISSING, "scope_not_authorized")

        with self.assertRaises(PlatformError):
            await self.tokens.valid(7)

        self.assertEqual((await self.accounts.get_account_tokens(7)).status, AccountStatus.NEEDS_REAUTH)

    async def test_an_outage_keeps_the_account_usable(self):
        self.given_account(expires_in=timedelta(0))
        self.authorization.refresh_answer = PlatformError(PlatformFailure.NETWORK, "unavailable")

        with self.assertRaises(PlatformError) as raised:
            await self.tokens.valid(7)

        self.assertTrue(raised.exception.transient)
        self.assertEqual((await self.accounts.get_account_tokens(7)).status, AccountStatus.ACTIVE)

    async def test_a_misconfigured_client_does_not_blame_the_account(self):
        # Given: our own client credentials are wrong
        self.given_account(expires_in=timedelta(0))
        self.authorization.refresh_answer = PlatformError(PlatformFailure.MISCONFIGURED, "invalid_client")

        # When / Then: the failure is reported, and the account stays active
        with self.assertRaises(PlatformError) as raised:
            await self.tokens.valid(7)
        self.assertEqual(raised.exception.failure, PlatformFailure.MISCONFIGURED)
        self.assertEqual((await self.accounts.get_account_tokens(7)).status, AccountStatus.ACTIVE)

    async def test_an_account_without_a_refresh_token_asks_for_reconnection(self):
        self.given_account(expires_in=timedelta(0), refresh_token="")

        with self.assertRaises(PlatformError):
            await self.tokens.valid(7)

        self.assertEqual(self.accounts.reasons[7], "No refresh token stored")
        self.assertEqual(self.authorization.refreshes, [])

    async def test_a_caller_waits_for_the_refresh_already_in_progress(self):
        # Given: another caller holds the lease and finishes while we wait
        account = self.given_account(expires_in=timedelta(0), lease_until=self.clock.now() + timedelta(minutes=1))
        later = account.expires_at + timedelta(hours=1)
        self.clock.on_sleep = lambda: self.accounts.change(7, access_token="theirs", expires_at=later, lease_until=None)

        # When / Then: we take their token without spending the refresh token
        self.assertEqual(await self.tokens.valid(7), "theirs")
        self.assertEqual(self.authorization.refreshes, [])

    async def test_a_refresh_that_never_finishes_elsewhere_is_transient(self):
        self.given_account(expires_in=timedelta(0), lease_until=self.clock.now() + timedelta(hours=1))

        with self.assertRaises(PlatformError) as raised:
            await self.tokens.valid(7)

        self.assertTrue(raised.exception.transient)

    async def test_the_periodic_refresh_counts_what_it_renewed(self):
        self.given_account(expires_in=timedelta(minutes=40))

        self.assertEqual(await self.tokens.refresh_expiring(), 1)
        self.assertEqual((await self.accounts.get_account_tokens(7)).access_token, "fresh")

    async def test_a_rejected_token_is_refreshed_once_and_the_call_repeated(self):
        # Given: the platform rejects the stored token
        self.given_account()
        seen: list[str] = []

        async def call(token: str) -> str:
            seen.append(token)
            if token == "stored":
                raise PlatformError(PlatformFailure.TOKEN_REJECTED, "expired")
            return "done"

        # When: a call runs with the account's token
        result = await self.tokens.run(7, call)

        # Then: it was repeated once with the refreshed token
        self.assertEqual(result, "done")
        self.assertEqual(seen, ["stored", "fresh"])


class AccountServiceScenarios(AccountScenarioBase):
    async def test_disconnecting_revokes_at_the_platform_and_forgets_the_tokens(self):
        self.given_account()

        await self.account_service.disconnect(7)

        self.assertEqual(self.authorization.revoked, [AuthToken("stored", "refresh-1")])
        tokens = await self.accounts.get_account_tokens(7)
        self.assertEqual((tokens.access_token, tokens.refresh_token, tokens.status), ("", "", AccountStatus.REVOKED))

    async def test_a_failed_revoke_still_disconnects(self):
        self.given_account()
        self.authorization.revoke_failure = PlatformError(PlatformFailure.NETWORK, "down")

        await self.account_service.disconnect(7)

        self.assertEqual((await self.accounts.get_account_tokens(7)).status, AccountStatus.REVOKED)

    async def test_an_account_without_tokens_is_not_revoked_at_the_platform(self):
        self.given_account(access_token="", refresh_token="")

        await self.account_service.disconnect(7)

        self.assertEqual(self.authorization.revoked, [])


class ConnectFlowScenarios(AccountScenarioBase):
    async def started(self, owner_id: int = 1) -> str:
        await self.flow.start(owner_id, FAKE.value)
        return self.sessions.only()["state"]

    async def test_an_unknown_platform_is_not_found(self):
        with self.assertRaises(NotFound):
            await self.flow.start(1, "myspace")

    async def test_an_unconfigured_platform_is_refused_before_a_session_is_opened(self):
        self.platform.configured = False

        with self.assertRaises(Unavailable):
            await self.flow.start(1, FAKE.value)

        self.assertEqual(self.sessions.rows, {})

    async def test_the_consent_url_carries_the_state_and_the_verifier_stays_on_the_server(self):
        url = await self.flow.start(1, FAKE.value)

        row = self.sessions.only()
        self.assertIn(f"state={row['state']}", url)
        self.assertEqual(row["verifier"], "the-verifier")
        self.assertNotIn("the-verifier", url)

    async def test_the_owner_completing_the_consent_connects_the_account(self):
        state = await self.started()

        outcome = await self.flow.complete(FAKE.value, state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.CONNECTED)
        self.assertEqual(self.accounts.saved[0][:2], (1, FAKE))
        self.assertEqual(self.authorization.exchanged, [("the-code", "the-verifier")])
        self.assertEqual(self.sessions.only()["status"], OAuthSessionStatus.DONE)

    async def test_a_state_opened_by_somebody_else_is_refused(self):
        state = await self.started(owner_id=1)

        outcome = await self.flow.complete(FAKE.value, state, "the-code", refused=False, requester_id=2)

        self.assertEqual(outcome, ConnectOutcome.INVALID)
        self.assertEqual(self.accounts.saved, [])
        self.assertEqual(self.authorization.exchanged, [])
        self.assertEqual(self.sessions.only()["status"], OAuthSessionStatus.ERROR)

    async def test_a_state_is_used_once(self):
        state = await self.started()
        await self.flow.complete(FAKE.value, state, "the-code", refused=False, requester_id=1)

        again = await self.flow.complete(FAKE.value, state, "the-code", refused=False, requester_id=1)

        self.assertEqual(again, ConnectOutcome.INVALID)
        self.assertEqual(len(self.accounts.saved), 1)

    async def test_an_expired_state_is_refused(self):
        state = await self.started()
        self.clock.advance(SESSION_TTL + timedelta(seconds=1))

        outcome = await self.flow.complete(FAKE.value, state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.INVALID)

    async def test_a_state_for_another_platform_is_refused(self):
        state = await self.started()

        outcome = await self.flow.complete("youtube", state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.INVALID)

    async def test_a_declined_consent_is_cancelled(self):
        state = await self.started()

        outcome = await self.flow.complete(FAKE.value, state, None, refused=True, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.CANCELLED)

    async def test_a_refused_exchange_fails_without_saving(self):
        state = await self.started()
        self.authorization.exchange_answer = PlatformError(PlatformFailure.GRANT_REVOKED, "invalid_grant")

        outcome = await self.flow.complete(FAKE.value, state, "the-code", refused=False, requester_id=1)

        self.assertEqual(outcome, ConnectOutcome.FAILED)
        self.assertEqual(self.accounts.saved, [])
        self.assertEqual(self.sessions.only()["status"], OAuthSessionStatus.ERROR)

from dataclasses import replace
from datetime import datetime

from platforms.core.auth import Identity, OAuth2Provider, TokenBundle
from platforms.core.auth.account import AccountRecord, AccountStatus, AccountTokens
from platforms.core.auth.session import OAuthSessionRecord, OAuthSessionStatus
from platforms.core.config import PlatformConfig
from platforms.core.errors import NotFound, ProviderError
from platforms.core.ports import AccountRepository, Clock, OAuthSessionRepository


class FakeAccounts(AccountRepository):
    def __init__(self, *accounts: AccountRecord):
        self.accounts = {account.id: account for account in accounts}
        self.tokens: dict[int, AccountTokens] = {}
        self.reasons: dict[int, str] = {}
        self.saved: list[tuple[int, str, TokenBundle, Identity]] = []

    def given_tokens(self, tokens: AccountTokens) -> AccountTokens:
        self.tokens[tokens.id] = tokens
        self.accounts[tokens.id] = AccountRecord(tokens.id, tokens.platform, tokens.status)
        return tokens

    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        return dict(self.accounts)

    def owned_account(self, owner_id: int, account_id: int, platform: str | None = None) -> AccountRecord:
        account = self.accounts.get(account_id)
        if account is None or (platform is not None and account.platform != platform):
            raise NotFound()
        return account

    def tokens_of(self, account_id: int) -> AccountTokens:
        return self.tokens[account_id]

    def save_connected(
        self, owner_id: int, platform: str, bundle: TokenBundle, identity: Identity, now: datetime
    ) -> int:
        self.saved.append((owner_id, platform, bundle, identity))
        return len(self.saved)

    def store_refreshed(
        self, account_id: int, previous_expiry: datetime | None, bundle: TokenBundle, now: datetime
    ) -> bool:
        if self.tokens[account_id].expires_at != previous_expiry:
            return False
        self._update(
            account_id,
            access_token=bundle.access_token,
            refresh_token=bundle.refresh_token or "",
            expires_at=bundle.expires_at(now),
            status=AccountStatus.ACTIVE,
        )
        return True

    def claim_refresh_lease(self, account_id: int, now: datetime, until: datetime) -> bool:
        lease = self.tokens[account_id].lease_until
        if lease is not None and lease >= now:
            return False
        self._update(account_id, lease_until=until)
        return True

    def release_refresh_lease(self, account_id: int, until: datetime) -> None:
        if self.tokens[account_id].lease_until == until:
            self._update(account_id, lease_until=None)

    def mark_needs_reauth(self, account_id: int, reason: str) -> None:
        self.reasons[account_id] = reason
        self._update(account_id, status=AccountStatus.NEEDS_REAUTH)

    def revoke(self, account_id: int) -> None:
        self._update(account_id, access_token="", refresh_token="", expires_at=None, status=AccountStatus.REVOKED)

    def expiring_before(self, moment: datetime) -> list[int]:
        return [
            account.id
            for account in self.tokens.values()
            if account.status == AccountStatus.ACTIVE and account.expires_at and account.expires_at < moment
        ]

    def _update(self, account_id: int, **fields) -> None:
        account = replace(self.tokens[account_id], **fields)
        self.tokens[account_id] = account
        self.accounts[account_id] = AccountRecord(account.id, account.platform, account.status)


class FakeSessions(OAuthSessionRepository):
    def __init__(self, clock: Clock):
        self._clock = clock
        self.rows: dict[int, dict] = {}

    def sweep_created_before(self, moment: datetime) -> int:
        expired = [pk for pk, row in self.rows.items() if row["created_at"] < moment]
        for pk in expired:
            del self.rows[pk]
        return len(expired)

    def create(self, owner_id: int, platform: str, state: str, code_verifier: str) -> OAuthSessionRecord:
        pk = max(self.rows, default=0) + 1
        self.rows[pk] = {
            "owner_id": owner_id,
            "platform": platform,
            "state": state,
            "verifier": code_verifier,
            "status": OAuthSessionStatus.PENDING,
            "created_at": self._clock.now(),
        }
        return OAuthSessionRecord(pk, owner_id, platform, code_verifier)

    def claim(self, platform: str, state: str, created_after: datetime) -> OAuthSessionRecord | None:
        for pk, row in self.rows.items():
            if row["platform"] != platform or row["state"] != state:
                continue
            if row["created_at"] < created_after or row["status"] != OAuthSessionStatus.PENDING:
                return None
            row["status"] = OAuthSessionStatus.PROCESSING
            return OAuthSessionRecord(pk, row["owner_id"], platform, row["verifier"])
        return None

    def finish(self, session_id: int, status: OAuthSessionStatus) -> None:
        self.rows[session_id]["status"] = status

    def only(self) -> dict:
        (row,) = self.rows.values()
        return row


class FakeProvider(OAuth2Provider):
    name = "fake"
    label = "Fake"
    scopes = ("video.publish",)
    authorize_endpoint = "https://fake.test/authorize"
    token_endpoint = "https://fake.test/token"

    def __init__(self):
        self.redirect_uri = "https://app.test/api/social/fake/callback"
        self.refreshes: list[str] = []
        self.refresh_answer: TokenBundle | ProviderError = TokenBundle("fresh", expires_in=3600)
        self.exchange_answer: TokenBundle | ProviderError = TokenBundle("first", "refresh-1", 3600)
        self.revoked: list[tuple[str, str]] = []
        self.revoke_failure: ProviderError | None = None

    @classmethod
    def create(cls, config: PlatformConfig):
        return cls()

    def client_id(self) -> str:
        return "client-id"

    def refresh(self, refresh_token: str) -> TokenBundle:
        self.refreshes.append(refresh_token)
        if isinstance(self.refresh_answer, ProviderError):
            raise self.refresh_answer
        return self.refresh_answer

    def exchange_code(self, code: str, code_verifier: str | None) -> TokenBundle:
        if isinstance(self.exchange_answer, ProviderError):
            raise self.exchange_answer
        return self.exchange_answer

    def fetch_identity(self, access_token: str) -> Identity:
        return Identity(external_id="fake-1", display_name="A Creator")

    def revoke(self, access_token: str, refresh_token: str) -> None:
        self.revoked.append((access_token, refresh_token))
        if self.revoke_failure is not None:
            raise self.revoke_failure

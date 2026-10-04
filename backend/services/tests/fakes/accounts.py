from dataclasses import replace
from datetime import datetime

from platforms.core import AuthProfile, AuthToken, PlatformType
from services.core.accounts import (
    AccountRecord,
    AccountStatus,
    AccountTokens,
    OAuthSessionRecord,
    OAuthSessionStatus,
)
from services.core.domain import NotFound
from services.core.ports import AccountRepository, Cache, Clock, OAuthSessionRepository


class FakeAccounts(AccountRepository):
    def __init__(self, *accounts: AccountRecord):
        self.accounts = {account.id: account for account in accounts}
        self.tokens: dict[int, AccountTokens] = {}
        self.reasons: dict[int, str] = {}
        self.saved: list[tuple[int, PlatformType, AuthToken, AuthProfile]] = []

    def given_tokens(self, tokens: AccountTokens) -> AccountTokens:
        self.tokens[tokens.id] = tokens
        self.accounts[tokens.id] = AccountRecord(tokens.id, tokens.platform, tokens.status)
        return tokens

    def change(self, account_id: int, **fields) -> None:
        account = replace(self.tokens[account_id], **fields)
        self.tokens[account_id] = account
        self.accounts[account_id] = AccountRecord(account.id, account.platform, account.status)

    async def get_connected_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        return {pk: account for pk, account in self.accounts.items() if account.status != AccountStatus.REVOKED}

    async def get_connected_account(self, owner_id: int, account_id: int) -> AccountRecord:
        account = (await self.get_connected_accounts(owner_id)).get(account_id)
        if account is None:
            raise NotFound()
        return account

    async def get_account_tokens(self, account_id: int) -> AccountTokens:
        return self.tokens[account_id]

    async def upsert_connected_account(
        self, owner_id: int, platform: PlatformType, token: AuthToken, profile: AuthProfile, now: datetime
    ) -> int:
        self.saved.append((owner_id, platform, token, profile))
        return len(self.saved)

    async def save_refreshed_tokens(self, account_id: int, token: AuthToken, now: datetime) -> None:
        self.change(
            account_id,
            access_token=token.access_token,
            refresh_token=token.refresh_token or "",
            expires_at=token.expires_at(now),
            status=AccountStatus.ACTIVE,
        )

    async def try_lock_token_refresh(self, account_id: int, now: datetime, until: datetime) -> bool:
        lease = self.tokens[account_id].lease_until
        if lease is not None and lease >= now:
            return False
        self.change(account_id, lease_until=until)
        return True

    async def unlock_token_refresh(self, account_id: int, until: datetime) -> None:
        if self.tokens[account_id].lease_until == until:
            self.change(account_id, lease_until=None)

    async def mark_needs_reauth(self, account_id: int, reason: str) -> None:
        self.reasons[account_id] = reason
        self.change(account_id, status=AccountStatus.NEEDS_REAUTH)

    async def clear_tokens_and_mark_revoked(self, account_id: int) -> None:
        self.change(account_id, access_token="", refresh_token="", expires_at=None, status=AccountStatus.REVOKED)

    async def find_active_expiring_before(self, moment: datetime) -> list[int]:
        return [
            account.id
            for account in self.tokens.values()
            if account.status == AccountStatus.ACTIVE and account.expires_at and account.expires_at < moment
        ]


class FakeSessions(OAuthSessionRepository):
    def __init__(self, clock: Clock):
        self._clock = clock
        self.rows: dict[int, dict] = {}

    async def delete_expired_sessions(self, moment: datetime) -> int:
        expired = [pk for pk, row in self.rows.items() if row["created_at"] < moment]
        for pk in expired:
            del self.rows[pk]
        return len(expired)

    async def start_session(
        self, owner_id: int, platform: PlatformType, state: str, code_verifier: str
    ) -> OAuthSessionRecord:
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

    async def claim_pending_session(
        self, platform: PlatformType, state: str, created_after: datetime
    ) -> OAuthSessionRecord | None:
        for pk, row in self.rows.items():
            if row["platform"] != platform or row["state"] != state:
                continue
            if row["created_at"] < created_after or row["status"] != OAuthSessionStatus.PENDING:
                return None
            row["status"] = OAuthSessionStatus.PROCESSING
            return OAuthSessionRecord(pk, row["owner_id"], platform, row["verifier"])
        return None

    async def finish_session(self, session_id: int, status: OAuthSessionStatus) -> None:
        self.rows[session_id]["status"] = status

    def only(self) -> dict:
        (row,) = self.rows.values()
        return row


class FakeCache(Cache):
    def __init__(self):
        self.values: dict[str, object] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value, seconds: int) -> None:
        self.values[key] = value

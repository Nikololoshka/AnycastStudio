from datetime import datetime

from django.db.models import Q

from common.encryption import current_key_version
from platforms.core.auth import Identity, TokenBundle
from platforms.core.auth.account import AccountRecord, AccountStatus, AccountTokens
from platforms.core.auth.session import OAuthSessionRecord, OAuthSessionStatus
from platforms.core.errors import NotFound
from platforms.core.ports import AccountRepository, OAuthSessionRepository

from .models import OAuthSession, SocialAccount


class DjangoAccountRepository(AccountRepository):
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        rows = SocialAccount.objects.filter(user_id=owner_id).values_list("pk", "platform", "status")
        return {pk: AccountRecord(pk, platform, AccountStatus(status)) for pk, platform, status in rows}

    def owned_account(self, owner_id: int, account_id: int, platform: str | None = None) -> AccountRecord:
        rows = SocialAccount.objects.filter(user_id=owner_id, pk=account_id).exclude(status=AccountStatus.REVOKED)
        if platform is not None:
            rows = rows.filter(platform=platform)
        row = rows.values_list("pk", "platform", "status").first()
        if row is None:
            raise NotFound()
        pk, platform, status = row
        return AccountRecord(pk, platform, AccountStatus(status))

    def tokens_of(self, account_id: int) -> AccountTokens:
        account = SocialAccount.objects.get(pk=account_id)
        return AccountTokens(
            id=account.pk,
            platform=account.platform,
            status=AccountStatus(account.status),
            access_token=account.access_token,
            refresh_token=account.refresh_token,
            expires_at=account.token_expires_at,
            lease_until=account.refresh_lease_until,
            scopes=tuple(account.scopes),
        )

    def save_connected(
        self, owner_id: int, platform: str, bundle: TokenBundle, identity: Identity, now: datetime
    ) -> int:
        account, _ = SocialAccount.objects.update_or_create(
            user_id=owner_id,
            platform=platform,
            external_id=identity.external_id,
            defaults={
                "display_name": identity.display_name,
                "avatar_url": identity.avatar_url,
                "access_token": bundle.access_token,
                "refresh_token": bundle.refresh_token or "",
                "key_version": current_key_version(),
                "token_expires_at": bundle.expires_at(now),
                "scopes": list(bundle.scopes),
                "extra": identity.extra,
                "status": AccountStatus.ACTIVE,
                "last_error": "",
                "connected_at": now,
            },
        )
        return account.pk

    def store_refreshed(
        self, account_id: int, previous_expiry: datetime | None, bundle: TokenBundle, now: datetime
    ) -> bool:
        return bool(
            SocialAccount.objects.filter(pk=account_id, token_expires_at=previous_expiry).update(
                access_token=bundle.access_token,
                refresh_token=bundle.refresh_token or "",
                key_version=current_key_version(),
                token_expires_at=bundle.expires_at(now),
                last_refresh_at=now,
                status=AccountStatus.ACTIVE,
                last_error="",
            )
        )

    def claim_refresh_lease(self, account_id: int, now: datetime, until: datetime) -> bool:
        free = Q(refresh_lease_until__isnull=True) | Q(refresh_lease_until__lt=now)
        return bool(SocialAccount.objects.filter(free, pk=account_id).update(refresh_lease_until=until))

    def release_refresh_lease(self, account_id: int, until: datetime) -> None:
        SocialAccount.objects.filter(pk=account_id, refresh_lease_until=until).update(refresh_lease_until=None)

    def mark_needs_reauth(self, account_id: int, reason: str) -> None:
        SocialAccount.objects.filter(pk=account_id).update(status=AccountStatus.NEEDS_REAUTH, last_error=reason[:500])

    def revoke(self, account_id: int) -> None:
        SocialAccount.objects.filter(pk=account_id).update(
            access_token="",
            refresh_token="",
            token_expires_at=None,
            status=AccountStatus.REVOKED,
            last_error="",
        )

    def expiring_before(self, moment: datetime) -> list[int]:
        return list(
            SocialAccount.objects.filter(
                status=AccountStatus.ACTIVE, token_expires_at__isnull=False, token_expires_at__lt=moment
            ).values_list("pk", flat=True)
        )


class DjangoOAuthSessionRepository(OAuthSessionRepository):
    def sweep_created_before(self, moment: datetime) -> int:
        deleted, _ = OAuthSession.objects.filter(created_at__lt=moment).delete()
        return deleted

    def create(self, owner_id: int, platform: str, state: str, code_verifier: str) -> OAuthSessionRecord:
        session = OAuthSession.objects.create(user_id=owner_id, platform=platform, state=state, code_verifier=code_verifier)
        return self._record(session)

    def claim(self, platform: str, state: str, created_after: datetime) -> OAuthSessionRecord | None:
        session = OAuthSession.objects.filter(platform=platform, state=state).first()
        if session is None or session.created_at < created_after:
            return None
        claimed = OAuthSession.objects.filter(pk=session.pk, status=OAuthSessionStatus.PENDING).update(
            status=OAuthSessionStatus.PROCESSING
        )
        return self._record(session) if claimed else None

    def finish(self, session_id: int, status: OAuthSessionStatus) -> None:
        OAuthSession.objects.filter(pk=session_id).update(status=status)

    @staticmethod
    def _record(session: OAuthSession) -> OAuthSessionRecord:
        return OAuthSessionRecord(session.pk, session.user_id, session.platform, session.code_verifier)

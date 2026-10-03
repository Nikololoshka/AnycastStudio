from datetime import datetime

from asgiref.sync import sync_to_async
from django.db.models import Q

from common.encryption import current_key_version
from platforms.core import AuthProfile, AuthToken, PlatformType
from platforms.core.accounts import (
    AccountRecord,
    AccountStatus,
    AccountTokens,
    OAuthSessionRecord,
    OAuthSessionStatus,
)
from platforms.core.domain import NotFound
from platforms.core.ports import AccountRepository, OAuthSessionRepository

from .models import OAuthSession, SocialAccount


class DjangoAccountRepository(AccountRepository):
    @sync_to_async
    def owned_accounts(self, owner_id: int) -> dict[int, AccountRecord]:
        rows = SocialAccount.objects.filter(user_id=owner_id).values_list("pk", "platform", "status")
        return {pk: AccountRecord(pk, PlatformType(platform), AccountStatus(status)) for pk, platform, status in rows}

    @sync_to_async
    def owned_account(self, owner_id: int, account_id: int, platform: PlatformType | None = None) -> AccountRecord:
        rows = SocialAccount.objects.filter(user_id=owner_id, pk=account_id).exclude(status=AccountStatus.REVOKED)
        if platform is not None:
            rows = rows.filter(platform=platform)
        row = rows.values_list("pk", "platform", "status").first()
        if row is None:
            raise NotFound()
        pk, platform_name, status = row
        return AccountRecord(pk, PlatformType(platform_name), AccountStatus(status))

    @sync_to_async
    def tokens_of(self, account_id: int) -> AccountTokens:
        account = SocialAccount.objects.get(pk=account_id)
        return AccountTokens(
            id=account.pk,
            platform=PlatformType(account.platform),
            status=AccountStatus(account.status),
            access_token=account.access_token,
            refresh_token=account.refresh_token,
            expires_at=account.token_expires_at,
            lease_until=account.refresh_lease_until,
            scopes=tuple(account.scopes),
        )

    @sync_to_async
    def save_connected(
        self, owner_id: int, platform: PlatformType, token: AuthToken, profile: AuthProfile, now: datetime
    ) -> int:
        account, _ = SocialAccount.objects.update_or_create(
            user_id=owner_id,
            platform=platform,
            external_id=profile.external_id,
            defaults={
                "display_name": profile.display_name,
                "avatar_url": profile.avatar_url,
                "access_token": token.access_token,
                "refresh_token": token.refresh_token or "",
                "key_version": current_key_version(),
                "token_expires_at": token.expires_at(now),
                "scopes": list(token.scopes),
                "status": AccountStatus.ACTIVE,
                "last_error": "",
                "connected_at": now,
            },
        )
        return account.pk

    @sync_to_async
    def store_refreshed(
        self, account_id: int, previous_expiry: datetime | None, token: AuthToken, now: datetime
    ) -> bool:
        return bool(
            SocialAccount.objects.filter(pk=account_id, token_expires_at=previous_expiry).update(
                access_token=token.access_token,
                refresh_token=token.refresh_token or "",
                key_version=current_key_version(),
                token_expires_at=token.expires_at(now),
                last_refresh_at=now,
                status=AccountStatus.ACTIVE,
                last_error="",
            )
        )

    @sync_to_async
    def claim_refresh_lease(self, account_id: int, now: datetime, until: datetime) -> bool:
        free = Q(refresh_lease_until__isnull=True) | Q(refresh_lease_until__lt=now)
        return bool(SocialAccount.objects.filter(free, pk=account_id).update(refresh_lease_until=until))

    @sync_to_async
    def release_refresh_lease(self, account_id: int, until: datetime) -> None:
        SocialAccount.objects.filter(pk=account_id, refresh_lease_until=until).update(refresh_lease_until=None)

    @sync_to_async
    def mark_needs_reauth(self, account_id: int, reason: str) -> None:
        SocialAccount.objects.filter(pk=account_id).update(status=AccountStatus.NEEDS_REAUTH, last_error=reason[:500])

    @sync_to_async
    def revoke(self, account_id: int) -> None:
        SocialAccount.objects.filter(pk=account_id).update(
            access_token="",
            refresh_token="",
            token_expires_at=None,
            status=AccountStatus.REVOKED,
            last_error="",
        )

    @sync_to_async
    def expiring_before(self, moment: datetime) -> list[int]:
        return list(
            SocialAccount.objects.filter(
                status=AccountStatus.ACTIVE, token_expires_at__isnull=False, token_expires_at__lt=moment
            ).values_list("pk", flat=True)
        )


class DjangoOAuthSessionRepository(OAuthSessionRepository):
    @sync_to_async
    def sweep_created_before(self, moment: datetime) -> int:
        deleted, _ = OAuthSession.objects.filter(created_at__lt=moment).delete()
        return deleted

    @sync_to_async
    def create(self, owner_id: int, platform: PlatformType, state: str, code_verifier: str) -> OAuthSessionRecord:
        session = OAuthSession.objects.create(
            user_id=owner_id, platform=platform, state=state, code_verifier=code_verifier
        )
        return self._record(session)

    @sync_to_async
    def claim(self, platform: PlatformType, state: str, created_after: datetime) -> OAuthSessionRecord | None:
        session = OAuthSession.objects.filter(platform=platform, state=state).first()
        if session is None or session.created_at < created_after:
            return None
        claimed = OAuthSession.objects.filter(pk=session.pk, status=OAuthSessionStatus.PENDING).update(
            status=OAuthSessionStatus.PROCESSING
        )
        return self._record(session) if claimed else None

    @sync_to_async
    def finish(self, session_id: int, status: OAuthSessionStatus) -> None:
        OAuthSession.objects.filter(pk=session_id).update(status=status)

    @staticmethod
    def _record(session: OAuthSession) -> OAuthSessionRecord:
        return OAuthSessionRecord(session.pk, session.user_id, PlatformType(session.platform), session.code_verifier)

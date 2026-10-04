from datetime import datetime

from asgiref.sync import sync_to_async

from platforms.core import PlatformType
from services.core.accounts import OAuthSessionRecord, OAuthSessionStatus
from services.core.ports import OAuthSessionRepository

from ..models import OAuthSession


class DjangoOAuthSessionRepository(OAuthSessionRepository):
    @sync_to_async
    def delete_expired_sessions(self, moment: datetime) -> int:
        deleted, _ = OAuthSession.objects.filter(created_at__lt=moment).delete()
        return deleted

    @sync_to_async
    def start_session(
        self, owner_id: int, platform: PlatformType, state: str, code_verifier: str
    ) -> OAuthSessionRecord:
        session = OAuthSession.objects.create(
            user_id=owner_id, platform=platform, state=state, code_verifier=code_verifier
        )
        return self._record(session)

    @sync_to_async
    def claim_pending_session(
        self, platform: PlatformType, state: str, created_after: datetime
    ) -> OAuthSessionRecord | None:
        session = OAuthSession.objects.filter(platform=platform, state=state).first()
        if session is None or session.created_at < created_after:
            return None
        claimed = OAuthSession.objects.filter(pk=session.pk, status=OAuthSessionStatus.PENDING).update(
            status=OAuthSessionStatus.PROCESSING
        )
        return self._record(session) if claimed else None

    @sync_to_async
    def finish_session(self, session_id: int, status: OAuthSessionStatus) -> None:
        OAuthSession.objects.filter(pk=session_id).update(status=status)

    @staticmethod
    def _record(session: OAuthSession) -> OAuthSessionRecord:
        return OAuthSessionRecord(session.pk, session.user_id, PlatformType(session.platform), session.code_verifier)

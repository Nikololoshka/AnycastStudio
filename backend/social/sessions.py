import logging
import secrets

from platforms.oauth import PlatformProvider, pkce

from .models import OAuthSession

logger = logging.getLogger(__name__)

Status = OAuthSession.Status


def _sweep_expired() -> None:
    deleted, _ = OAuthSession.objects.filter(created_at__lt=OAuthSession.expiry_cutoff()).delete()
    if deleted:
        logger.info("Removed %d expired OAuth sessions", deleted)


def create(user, provider: PlatformProvider) -> tuple[OAuthSession, str | None]:
    _sweep_expired()

    verifier = pkce.generate_verifier() if provider.uses_pkce else ""
    session = OAuthSession.objects.create(
        user=user,
        platform=provider.name,
        state=secrets.token_urlsafe(32),
        code_verifier=verifier,
    )
    logger.info("OAuth session %s started for %s", session.pk, provider.name)
    return session, provider.code_challenge(verifier) if verifier else None


def claim(platform: str, state: str) -> OAuthSession | None:
    if not state:
        return None

    session = OAuthSession.objects.filter(platform=platform, state=state).first()
    if session is None or session.is_expired:
        return None

    claimed = OAuthSession.objects.filter(pk=session.pk, status=Status.PENDING).update(
        status=Status.PROCESSING
    )
    return session if claimed else None


def finish(session: OAuthSession, status: str) -> None:
    OAuthSession.objects.filter(pk=session.pk).update(status=status)
    logger.info("OAuth session %s finished as %s", session.pk, status)

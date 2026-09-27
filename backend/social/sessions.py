"""The OAuth session lifecycle: pending -> processing -> done | error.

All database work for connecting an account happens here. `claim` is a
conditional UPDATE rather than a lock, because SQLite has no
SELECT ... FOR UPDATE SKIP LOCKED and the pattern ports unchanged to Postgres.
"""

import logging
import secrets

from platforms.oauth import pkce

from .models import OAuthSession

logger = logging.getLogger(__name__)

Status = OAuthSession.Status


def create(user, platform: str, uses_pkce: bool) -> tuple[OAuthSession, str | None]:
    """Start a session and return it with the code challenge to send the browser."""
    deleted, _ = OAuthSession.objects.filter(created_at__lt=OAuthSession.expiry_cutoff()).delete()
    if deleted:
        logger.info("Removed %d expired OAuth sessions", deleted)

    verifier = pkce.generate_verifier() if uses_pkce else ""
    session = OAuthSession.objects.create(
        user=user,
        platform=platform,
        state=secrets.token_urlsafe(32),
        code_verifier=verifier,
    )
    logger.info("OAuth session %s started for %s", session.pk, platform)
    return session, pkce.s256_challenge(verifier) if verifier else None


def claim(platform: str, state: str) -> OAuthSession | None:
    """Take a pending session for the callback, or None if it is unknown, expired or used.

    The status change is a conditional UPDATE, so two callbacks carrying the
    same state cannot both proceed.
    """
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

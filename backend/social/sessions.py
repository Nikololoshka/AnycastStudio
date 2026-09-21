"""pending -> processing (callback claimed it) -> done | error -> deleted (result handed to /poll)"""

import logging
import secrets

from .models import AuthSession, hash_token

logger = logging.getLogger(__name__)

Status = AuthSession.Status
FINISHED = (Status.DONE, Status.ERROR)


def create(provider_name: str) -> tuple[str, str]:
    deleted, _ = AuthSession.objects.filter(created_at__lt=AuthSession.expiry_cutoff()).delete()
    if deleted:
        logger.info("Removed %d expired auth sessions", deleted)

    state = secrets.token_urlsafe(32)
    poll_token = secrets.token_urlsafe(32)
    session = AuthSession.objects.create(
        provider=provider_name,
        state=state,
        poll_token_hash=hash_token(poll_token),
    )
    logger.info("Auth session %s started for %s", session.pk, provider_name)
    return state, poll_token


def claim(provider_name: str, state: str) -> AuthSession | None:
    """Take a pending session for callback processing, or None if it is unknown, expired or used.

    The status change is a conditional UPDATE, so two callbacks with the same state cannot both claim it.
    """
    if not state:
        return None
    session = AuthSession.objects.filter(provider=provider_name, state=state).first()
    if session is None or session.is_expired:
        return None
    claimed = AuthSession.objects.filter(pk=session.pk, status=Status.PENDING).update(status=Status.PROCESSING)
    return session if claimed else None


def finish(session: AuthSession, status: str, result: dict) -> None:
    AuthSession.objects.filter(pk=session.pk).update(status=status, result=result)
    logger.info("Auth session %s finished as %s", session.pk, status)


def complete(session: AuthSession, result: dict) -> None:
    finish(session, Status.DONE, result)


def fail(session: AuthSession, result: dict) -> None:
    finish(session, Status.ERROR, result)


async def check(provider_name: str, poll_token: str) -> tuple[str, dict]:
    """Look at a session once, for /poll: ("not_found" | "expired" | "pending" | "done" | "error", fields).

    A finished result is returned only once: the session is deleted when it is handed out.
    """
    lookup = AuthSession.objects.filter(provider=provider_name, poll_token_hash=hash_token(poll_token))
    session = await lookup.afirst()

    if session is None:
        return "not_found", {}
    if session.is_expired:
        await lookup.adelete()
        return "expired", {}
    if session.status not in FINISHED:
        return "pending", {}

    # Two concurrent polls may both see the result; only the one that deletes the row returns it.
    deleted, _ = await lookup.filter(status__in=FINISHED).adelete()
    if not deleted:
        return "not_found", {}
    return session.status, session.result or {}

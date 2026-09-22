"""Where the platform sends the browser back.

This is a GET the provider redirects to, so it cannot carry a CSRF token; the
`state` parameter is the defence, and it is checked twice — that it is a
session we issued and still pending, and that it belongs to the person whose
session cookie is on this request.
"""

import logging

from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

from platforms.base import ProviderError

from .. import services, sessions
from ..providers import get_provider

logger = logging.getLogger(__name__)

RETURN_PATH = "/settings/accounts"


def back_to_app(platform: str, outcome: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{RETURN_PATH}?platform={platform}&result={outcome}")


@require_GET
def callback(request, platform: str):
    provider = get_provider(platform)
    if provider is None:
        return back_to_app(platform, "invalid")

    session = sessions.claim(provider.name, request.GET.get("state", ""))
    if session is None:
        return back_to_app(platform, "invalid")

    # The state was ours, but this browser must also be the one that asked for it.
    if not request.user.is_authenticated or session.user_id != request.user.pk:
        sessions.finish(session, sessions.Status.ERROR)
        logger.warning("OAuth session %s was opened by a different session", session.pk)
        return back_to_app(platform, "invalid")

    code = request.GET.get("code")
    if request.GET.get("error") or not code:
        sessions.finish(session, sessions.Status.ERROR)
        return back_to_app(platform, "cancelled")

    try:
        bundle = provider.exchange_code(code, session.code_verifier or None)
        identity = provider.fetch_identity(bundle.access_token)
    except ProviderError as error:
        sessions.finish(session, sessions.Status.ERROR)
        logger.info("OAuth session %s failed: %s", session.pk, error.message)
        return back_to_app(platform, "failed")
    except Exception:
        # Never let the traceback reach the browser: it can contain the request
        # body of the token exchange, which carries client_secret.
        logger.exception("OAuth session %s: unexpected error", session.pk)
        sessions.finish(session, sessions.Status.ERROR)
        return back_to_app(platform, "failed")

    services.save_account(session.user, provider.name, bundle, identity)
    sessions.finish(session, sessions.Status.DONE)
    return back_to_app(platform, "connected")

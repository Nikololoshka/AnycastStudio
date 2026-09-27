import logging
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

from platforms.oauth import ProviderError

from .. import services, sessions
from ..providers import PROVIDERS

logger = logging.getLogger(__name__)

RETURN_PATH = "/settings/accounts"


def back_to_app(platform: str, outcome: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{RETURN_PATH}?platform={platform}&result={outcome}")


def _arrived_off_the_app_origin(request) -> bool:
    return request.get_host() != urlparse(settings.PUBLIC_ORIGIN).netloc


def _on_to_the_app_origin(request) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{settings.PUBLIC_ORIGIN}{request.get_full_path()}")


def _opened_by_this_browser(request, session) -> bool:
    return request.user.is_authenticated and session.user_id == request.user.pk


@require_GET
def social_callback(request, platform: str):
    if _arrived_off_the_app_origin(request):
        return _on_to_the_app_origin(request)

    provider = PROVIDERS.get(platform)
    if provider is None:
        return back_to_app(platform, "invalid")

    session = sessions.claim(provider.name, request.GET.get("state", ""))
    if session is None:
        return back_to_app(platform, "invalid")

    if not _opened_by_this_browser(request, session):
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
        logger.exception("OAuth session %s: unexpected error", session.pk)
        sessions.finish(session, sessions.Status.ERROR)
        return back_to_app(platform, "failed")

    services.save_account(session.user, provider.name, bundle, identity)
    sessions.finish(session, sessions.Status.DONE)
    return back_to_app(platform, "connected")

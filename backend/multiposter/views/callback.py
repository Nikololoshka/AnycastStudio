import logging

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .. import sessions
from ..providers import PROVIDERS, ExchangeError

logger = logging.getLogger(__name__)


def page(request, outcome, status=200):
    return render(request, "multiposter/callback.html", {"outcome": outcome}, status=status)


def denied_result(params) -> dict:
    result = {"error": (params.get("error") or "missing_code")[:200]}
    if params.get("error_reason"):
        result["error_reason"] = params["error_reason"][:200]
    return result


@require_GET
def callback(request, provider):
    provider = PROVIDERS[provider]
    params = request.GET

    session = sessions.claim(provider.name, params.get("state", ""))
    if session is None:
        return page(request, "invalid", status=400)

    code = params.get("code")
    if params.get("error") or not code:
        sessions.fail(session, denied_result(params))
        return page(request, "cancelled")

    try:
        token = provider.exchange_code(code)
    except ExchangeError as exc:
        sessions.fail(session, {"error": provider.error_code, "message": exc.message})
        return page(request, "failed", status=502)
    except Exception:
        logger.exception("Auth session %s: unexpected error during token exchange", session.pk)
        sessions.fail(session, {"error": "server_error"})
        return page(request, "failed", status=500)

    sessions.complete(session, {"provider": provider.name, **token})
    return page(request, "done")

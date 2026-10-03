from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

from config.wiring import container

RETURN_PATH = "/settings/accounts"


def back_to_app(platform: str, outcome: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{RETURN_PATH}?platform={platform}&result={outcome}")


def _arrived_off_the_app_origin(request) -> bool:
    return request.get_host() != urlparse(settings.PUBLIC_ORIGIN).netloc


def _on_to_the_app_origin(request) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{settings.PUBLIC_ORIGIN}{request.get_full_path()}")


def _requester_of(request) -> int | None:
    return request.user.pk if request.user.is_authenticated else None


@require_GET
def social_callback(request, platform: str):
    if _arrived_off_the_app_origin(request):
        return _on_to_the_app_origin(request)

    state = request.GET.get("state", "")
    code = request.GET.get("code")
    refused = bool(request.GET.get("error"))
    requester_id = _requester_of(request)
    outcome = container().run(
        lambda services: services.connect_flow.complete(platform, state, code, refused, requester_id)
    )
    return back_to_app(platform, outcome)

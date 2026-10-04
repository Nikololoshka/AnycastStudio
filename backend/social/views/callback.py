from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

from services.wiring import container

RETURN_PATH = "/settings/accounts"


@require_GET
def social_complete_connection(request, platform: str):
    if request.get_host() != urlparse(settings.PUBLIC_ORIGIN).netloc:
        return HttpResponseRedirect(f"{settings.PUBLIC_ORIGIN}{request.get_full_path()}")

    state = request.GET.get("state", "")
    code = request.GET.get("code")
    refused = bool(request.GET.get("error"))
    requester_id = request.user.pk

    outcome = container().run(
        lambda services: services.connect_flow.complete(platform, state, code, refused, requester_id)
    )

    return HttpResponseRedirect(f"{RETURN_PATH}?platform={platform}&result={outcome}")

from common.access import require_auth, require_get
from common.responses import api_response
from platforms import youtube

CAPABILITIES = {"youtube": youtube.capabilities}


@require_get
@require_auth
def publishing_platforms(request):
    return api_response(
        "ok",
        platforms={name: build().as_json() for name, build in CAPABILITIES.items()},
    )

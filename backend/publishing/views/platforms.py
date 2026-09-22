"""What the browser needs to know about each platform.

Served from here rather than duplicated in the frontend, so the capability the
composer shows and the capability the server enforces cannot drift apart.
"""

from common.guards import require_auth, require_get
from common.responses import api_response
from platforms import youtube

CAPABILITIES = {"youtube": youtube.capabilities}


@require_get
@require_auth
def platforms(request):
    return api_response(
        "ok",
        platforms={name: build().as_json() for name, build in CAPABILITIES.items()},
    )

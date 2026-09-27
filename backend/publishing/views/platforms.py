from common.access import require_auth, require_get
from common.responses import api_response

from ..publishers import PUBLISHERS


@require_get
@require_auth
def publishing_platforms(request):
    return api_response(
        "ok",
        platforms={name: publisher.capabilities().as_json() for name, publisher in PUBLISHERS.items()},
    )

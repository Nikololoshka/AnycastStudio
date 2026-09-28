from common.access import require_auth, require_get
from common.responses import api_response
from config.wiring import container


@require_get
@require_auth
def publishing_platforms(request):
    catalog = container().catalog
    return api_response("ok", platforms={platform.name: platform.capabilities.as_json() for platform in catalog.all()})

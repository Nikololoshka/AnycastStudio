from common.access import require_auth, require_get
from common.responses import api_response
from platforms import PlatformCatalog


@require_get
@require_auth
def publishing_list_platform_capabilities(request):
    platforms = {
        platform_type.value: capabilities.as_json()
        for platform_type, capabilities in PlatformCatalog.capabilities_by_platform().items()
    }
    return api_response("ok", platforms=platforms)

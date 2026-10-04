from common.access import require_auth, require_get
from common.responses import api_response
from services.wiring import container


@require_get
@require_auth
def publishing_platforms(request):
    platforms = container().run(_capabilities)
    return api_response("ok", platforms=platforms)


async def _capabilities(services) -> dict:
    return {platform.platform_type.value: platform.capabilities.as_json() for platform in services.catalog.all()}

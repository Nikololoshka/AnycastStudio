import asyncio
import time

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .. import sessions
from .common import api_response, bearer_token, rate_limit, require_post, unauthorized_response


@csrf_exempt
@require_post
@rate_limit("poll")
async def poll(request, provider):
    token = bearer_token(request)
    if token is None:
        return unauthorized_response()

    deadline = time.monotonic() + settings.POLL_TIMEOUT
    while True:
        status, data = await sessions.check(provider, token)
        if status != "pending":
            return api_response(status, **data)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return api_response("pending")
        await asyncio.sleep(min(settings.POLL_INTERVAL, remaining))

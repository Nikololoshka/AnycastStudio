from ..guard import guard
from ..responses import api_response
from .counter import is_rate_limited


def rate_limit(scope: str):
    @guard
    def decorator(request, *args, **kwargs):
        if is_rate_limited(request, scope):
            return api_response("rate_limited")

    return decorator

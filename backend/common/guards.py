import inspect
from functools import wraps

from .ratelimit import is_rate_limited
from .responses import api_response


def guard(check):
    def decorator(view):
        if inspect.iscoroutinefunction(view):

            @wraps(view)
            async def wrapper(request, *args, **kwargs):
                return check(request, *args, **kwargs) or await view(request, *args, **kwargs)

        else:

            @wraps(view)
            def wrapper(request, *args, **kwargs):
                return check(request, *args, **kwargs) or view(request, *args, **kwargs)

        return wrapper

    return decorator


def require_method(method: str):
    @guard
    def decorator(request, *args, **kwargs):
        if request.method != method:
            return api_response("method_not_allowed", headers={"Allow": method})

    return decorator


require_post = require_method("POST")
require_get = require_method("GET")
require_delete = require_method("DELETE")


@guard
def require_auth(request, *args, **kwargs):
    if not request.user.is_authenticated:
        return api_response("unauthorized")


def rate_limit(scope: str):
    @guard
    def decorator(request, *args, **kwargs):
        if is_rate_limited(request, scope):
            return api_response("rate_limited")

    return decorator


__all__ = [
    "guard",
    "rate_limit",
    "require_auth",
    "require_delete",
    "require_get",
    "require_method",
    "require_post",
]

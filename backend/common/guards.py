"""Decorators that reject a request before the view runs.

`guard` turns a plain check into a decorator that works on sync and async
views alike, which is why the project does not need a framework layer here.
A check returns a response to stop the request, or None to let it through.
"""

import inspect
from functools import wraps

from .ratelimit import is_rate_limited
from .responses import api_response, unauthorized_response


def guard(check):
    """Turn `check(request, **kwargs) -> JsonResponse | None` into a decorator for sync and async views."""

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


def bearer_token(request) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


__all__ = [
    "bearer_token",
    "guard",
    "rate_limit",
    "require_auth",
    "require_delete",
    "require_get",
    "require_method",
    "require_post",
    "unauthorized_response",
]

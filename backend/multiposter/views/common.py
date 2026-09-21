import hmac
import inspect
from functools import wraps

from django.conf import settings
from django.http import JsonResponse

from ..ratelimit import is_rate_limited

HTTP_STATUS = {
    "unauthorized": 401,
    "not_found": 404,
    "method_not_allowed": 405,
    "expired": 410,
    "rate_limited": 429,
    "server_error": 500,
}


def api_response(status: str, headers=None, **fields) -> JsonResponse:
    return JsonResponse({"status": status, **fields}, status=HTTP_STATUS.get(status, 200), headers=headers)


def unauthorized_response() -> JsonResponse:
    return api_response("unauthorized", headers={"WWW-Authenticate": "Bearer"})


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


@guard
def require_post(request, *args, **kwargs):
    if request.method != "POST":
        return api_response("method_not_allowed", headers={"Allow": "POST"})


def rate_limit(scope: str):
    @guard
    def decorator(request, *args, **kwargs):
        if is_rate_limited(request, scope):
            return api_response("rate_limited")

    return decorator


@guard
def require_client_token(request, *args, **kwargs):
    token = bearer_token(request)
    if token is None:
        return unauthorized_response()
    # Every token is compared, without short-circuiting, so timing does not reveal which one matched.
    matches = [hmac.compare_digest(token.encode(), known.encode()) for known in settings.CLIENT_TOKENS]
    if not any(matches):
        return unauthorized_response()


def bearer_token(request) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def not_found(request, exception=None):
    return api_response("not_found")


def server_error(request):
    return api_response("server_error")

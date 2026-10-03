import inspect
from functools import wraps

from platforms2.core.domain import (
    AccountNeedsReauth,
    Conflict,
    DomainError,
    Invalid,
    LimitReached,
    NotFound,
    Unavailable,
)

from .contract import api_response

DOMAIN_STATUS = {
    NotFound: "not_found",
    Invalid: "invalid",
    Conflict: "conflict",
    LimitReached: "quota_exceeded",
    AccountNeedsReauth: "conflict",
    Unavailable: "server_error",
}


def response_of(error: DomainError):
    return api_response(DOMAIN_STATUS[type(error)], **error.fields)


def domain_errors(view):
    if inspect.iscoroutinefunction(view):

        @wraps(view)
        async def wrapper(request, *args, **kwargs):
            try:
                return await view(request, *args, **kwargs)
            except DomainError as error:
                return response_of(error)

    else:

        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except DomainError as error:
                return response_of(error)

    return wrapper

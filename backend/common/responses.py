"""The JSON contract every endpoint answers with.

A response always carries a `status` string; the HTTP code follows from it.
Clients branch on the string, so adding an outcome means adding a row here
rather than inventing a new body shape.
"""

from django.http import JsonResponse

HTTP_STATUS = {
    "invalid": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "expired": 410,
    "payload_too_large": 413,
    "quota_exceeded": 409,
    "rate_limited": 429,
    "server_error": 500,
}


def api_response(status: str, headers=None, **fields) -> JsonResponse:
    return JsonResponse({"status": status, **fields}, status=HTTP_STATUS.get(status, 200), headers=headers)


def unauthorized_response() -> JsonResponse:
    return api_response("unauthorized", headers={"WWW-Authenticate": "Bearer"})


def not_found(request, exception=None):
    return api_response("not_found")


def server_error(request):
    return api_response("server_error")

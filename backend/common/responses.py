from django.http import JsonResponse

HTTP_STATUS = {
    "ok": 200,
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
    return JsonResponse({"status": status, **fields}, status=HTTP_STATUS[status], headers=headers)


def bad_request(request, exception=None):
    return api_response("invalid")


def permission_denied(request, exception=None):
    return api_response("forbidden")


def csrf_failure(request, reason=""):
    return api_response("forbidden")


def not_found(request, exception=None):
    return api_response("not_found")


def server_error(request):
    return api_response("server_error")

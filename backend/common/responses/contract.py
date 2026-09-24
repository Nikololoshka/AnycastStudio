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

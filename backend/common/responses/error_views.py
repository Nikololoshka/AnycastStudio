from .contract import api_response


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

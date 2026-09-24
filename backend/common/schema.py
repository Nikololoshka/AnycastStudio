import json
from functools import wraps

from pydantic import BaseModel, ValidationError

from .responses import api_response


def _field_path(error) -> str:
    return ".".join(str(part) for part in error["loc"])


def _errors_of(exception: ValidationError) -> list[dict]:
    return [{"field": _field_path(error), "message": error["msg"]} for error in exception.errors()]


def validate(model: type[BaseModel]):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                payload = json.loads(request.body or b"{}")
            except (ValueError, RecursionError):
                return api_response("invalid", errors=[{"field": "", "message": "body is not valid JSON"}])

            if not isinstance(payload, dict):
                return api_response("invalid", errors=[{"field": "", "message": "body must be an object"}])

            try:
                data = model(**payload)
            except ValidationError as exception:
                return api_response("invalid", errors=_errors_of(exception))

            return view(request, *args, data=data, **kwargs)

        return wrapper

    return decorator

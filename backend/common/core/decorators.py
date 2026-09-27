import inspect
from functools import wraps


def _run_before(view, check):
    if inspect.iscoroutinefunction(view):

        @wraps(view)
        async def wrapper(request, *args, **kwargs):
            return check(request) or await view(request, *args, **kwargs)

    else:

        @wraps(view)
        def wrapper(request, *args, **kwargs):
            return check(request) or view(request, *args, **kwargs)

    return wrapper


def precondition(check):
    def decorator(view):
        return _run_before(view, check)

    return decorator


def precondition_with_params(check):
    def bind(*params):
        return precondition(lambda request: check(request, *params))

    return bind

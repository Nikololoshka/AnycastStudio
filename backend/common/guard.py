import inspect
from functools import wraps


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

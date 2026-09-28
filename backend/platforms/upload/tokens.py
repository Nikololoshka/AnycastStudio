from ..core.errors import FailureType, NeedsFreshToken, PlatformError


def fresh_token_on_rejection(action, state=None):
    try:
        return action()
    except NeedsFreshToken:
        raise
    except PlatformError as failure:
        if failure.type == FailureType.AUTHENTICATION:
            raise NeedsFreshToken(state.as_dict() if state is not None else None, failure.message) from None
        raise

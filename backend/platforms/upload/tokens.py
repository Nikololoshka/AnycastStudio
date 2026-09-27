from ..http import AUTHENTICATION, PlatformFailure
from .errors import NeedsFreshToken


def fresh_token_on_rejection(action, state=None):
    try:
        return action()
    except PlatformFailure as failure:
        if failure.type == AUTHENTICATION:
            raise NeedsFreshToken(state.as_dict() if state is not None else None, failure.message) from None
        raise

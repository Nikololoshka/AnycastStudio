from ..errors import FailureType, NeedsFreshToken, PlatformError
from .state import ResumableState


class TokenRejectionGuard:
    def __init__(self, state: ResumableState | None = None):
        self._state = state

    def run(self, action):
        try:
            return action()
        except NeedsFreshToken:
            raise
        except PlatformError as failure:
            if failure.type == FailureType.AUTHENTICATION:
                raise NeedsFreshToken(self._resume_point(), failure.message) from None
            raise

    def _resume_point(self) -> dict | None:
        return self._state.as_dict() if self._state is not None else None

from .auth_failure import AuthFailure


class AuthorizationError(Exception):
    def __init__(self, failure: AuthFailure, message: str):
        super().__init__(message)
        self.failure = failure
        self.message = message

    @property
    def transient(self) -> bool:
        return self.failure.transient

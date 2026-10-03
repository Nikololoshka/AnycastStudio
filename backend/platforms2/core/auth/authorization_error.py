class AuthorizationError(Exception):
    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.message = message
        self.transient = transient

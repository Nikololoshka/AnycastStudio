class Cancelled(Exception):
    def __init__(self, state):
        super().__init__("cancelled")
        self.state = state


class NeedsFreshToken(Exception):
    def __init__(self, state, message: str):
        super().__init__(message)
        self.state = state

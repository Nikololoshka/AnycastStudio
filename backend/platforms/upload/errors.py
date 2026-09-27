class UploadCancelled(Exception):
    def __init__(self, state: dict):
        super().__init__("cancelled")
        self.state = state


class NeedsFreshToken(Exception):
    def __init__(self, state: dict | None, message: str):
        super().__init__(message)
        self.state = state

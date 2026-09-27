from dataclasses import dataclass


class Interrupted(Exception):
    def __init__(self, state: dict, message: str = ""):
        super().__init__(message)
        self.state = state


class UploadCancelled(Interrupted):
    pass


class NeedsFreshToken(Interrupted):
    pass


@dataclass(frozen=True)
class Published:
    status: str
    url: str = ""
    resume_state: dict | None = None

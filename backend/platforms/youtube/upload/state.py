from dataclasses import dataclass

from ...core.upload import ResumableState


@dataclass(frozen=True)
class ResumeState(ResumableState):
    session_uri: str
    offset: int = 0

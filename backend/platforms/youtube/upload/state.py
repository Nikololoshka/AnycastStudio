from dataclasses import dataclass

from ...core.upload import ResumableState


@dataclass
class ResumeState(ResumableState):
    session_uri: str
    offset: int = 0

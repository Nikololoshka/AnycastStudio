from dataclasses import dataclass


@dataclass(frozen=True)
class Published:
    status: str
    url: str = ""
    resume_state: dict | None = None

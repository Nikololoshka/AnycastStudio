from dataclasses import dataclass


@dataclass(frozen=True)
class Scheduled:
    url: str = ""

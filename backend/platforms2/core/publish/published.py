from dataclasses import dataclass


@dataclass(frozen=True)
class Published:
    url: str = ""

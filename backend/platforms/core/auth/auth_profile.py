from dataclasses import dataclass


@dataclass(frozen=True)
class AuthProfile:
    external_id: str
    display_name: str
    avatar_url: str = ""

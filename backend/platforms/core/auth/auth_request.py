from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthRequest:
    url: str
    state: str
    code_verifier: str = field(repr=False)

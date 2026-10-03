from .domain_error import DomainError


class LimitReached(DomainError):
    def __init__(self, message: str, limit: int):
        super().__init__(message=message, limit=limit)

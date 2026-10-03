from .domain_error import DomainError


class Conflict(DomainError):
    def __init__(self, message: str, **fields):
        super().__init__(message=message, **fields)

from .domain_error import DomainError


class Unavailable(DomainError):
    def __init__(self, message: str):
        super().__init__(message=message)

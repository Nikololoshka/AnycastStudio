from .domain_error import DomainError


class NotFound(DomainError):
    def __init__(self, message: str = ""):
        super().__init__(**({"message": message} if message else {}))

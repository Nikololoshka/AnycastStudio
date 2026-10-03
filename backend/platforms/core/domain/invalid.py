from .domain_error import DomainError


class Invalid(DomainError):
    def __init__(self, field: str, message: str):
        super().__init__(errors=[{"field": field, "message": message}])

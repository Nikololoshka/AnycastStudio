from .domain_error import DomainError


class AccountNeedsReauth(DomainError):
    def __init__(self, platform: str):
        super().__init__(message="account_needs_reauth", platform=platform)

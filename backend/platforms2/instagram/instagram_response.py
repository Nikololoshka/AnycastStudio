from platforms2.core import AuthFailure, PlatformResponse


class InstagramResponse(PlatformResponse):
    REFUSAL_LIMIT = 200
    TOKEN_REJECTED_CODES = (102, 190)
    MISCONFIGURED_CODES = (101, 191)
    PERMISSION_CODES = (10, *range(200, 300))
    THROTTLED_CODES = (4, 17, 32, 613)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self._graph_error()

    def failure(self) -> AuthFailure:
        code = self._graph_error().get("code")
        if code in self.TOKEN_REJECTED_CODES:
            return AuthFailure.TOKEN_REJECTED
        if code in self.MISCONFIGURED_CODES:
            return AuthFailure.MISCONFIGURED
        if code in self.PERMISSION_CODES:
            return AuthFailure.SCOPE_MISSING
        if code in self.THROTTLED_CODES or self.status == 429:
            return AuthFailure.RATE_LIMITED
        if self.status == 408 or self.status >= 500:
            return AuthFailure.NETWORK
        if self.status == 401:
            return AuthFailure.TOKEN_REJECTED
        return AuthFailure.REFUSED

    def refusal(self) -> str:
        error = self._graph_error()
        message = error.get("error_user_msg") or error.get("message")
        if message:
            return str(message)[: self.REFUSAL_LIMIT]
        return f"HTTP {self.status}"

    def _graph_error(self) -> dict:
        error = self.body.get("error")
        return error if isinstance(error, dict) else {}

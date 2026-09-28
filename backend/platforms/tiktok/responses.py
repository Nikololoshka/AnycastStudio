from ..core.http import PlatformModel

OK_CODE = "ok"


class EnvelopeError(PlatformModel):
    code: str = ""
    message: str = ""

    @property
    def refused(self) -> bool:
        return self.code not in ("", OK_CODE)


class Envelope(PlatformModel):
    error: EnvelopeError = EnvelopeError()
    data: dict = {}

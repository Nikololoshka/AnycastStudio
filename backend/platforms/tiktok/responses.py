from ..core.http import PlatformModel, Present

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


class InitData(PlatformModel):
    publish_id: Present
    upload_url: Present


class User(PlatformModel):
    open_id: Present
    display_name: str = ""
    avatar_url: str = ""


class UserData(PlatformModel):
    user: User

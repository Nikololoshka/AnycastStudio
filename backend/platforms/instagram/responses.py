from typing import Annotated

from pydantic import BeforeValidator

from ..http import PlatformModel, Present

FINISHED = "FINISHED"
PUBLISHED = "PUBLISHED"
ERROR = "ERROR"
EXPIRED = "EXPIRED"


def _count(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    return int(value) if str(value).isdigit() else None


Count = Annotated[int | None, BeforeValidator(_count)]


class GraphError(PlatformModel):
    code: int | None = None
    error_subcode: int | None = None
    message: str = ""
    error_user_msg: str = ""

    @property
    def details(self) -> str:
        if self.code and self.error_subcode:
            return f"{self.code}/{self.error_subcode}"
        return str(self.code or "")


class ErrorAnswer(PlatformModel):
    error: GraphError | None = None
    debug_info: GraphError | None = None

    @property
    def graph_error(self) -> GraphError | None:
        for error in (self.error, self.debug_info):
            if error is not None and error.model_fields_set:
                return error
        return None


class UserToken(PlatformModel):
    access_token: Present


class Created(PlatformModel):
    id: Present


class Chunk(PlatformModel):
    success: bool = False


class UploadingPhase(PlatformModel):
    bytes_transferred: Count = None


class VideoStatus(PlatformModel):
    uploading_phase: UploadingPhase = UploadingPhase()


class ContainerStatus(PlatformModel):
    status_code: str = ""
    status: str = ""
    video_status: VideoStatus = VideoStatus()

    @property
    def bytes_transferred(self) -> int | None:
        return self.video_status.uploading_phase.bytes_transferred

    @property
    def is_ready(self) -> bool:
        return self.status_code == FINISHED

    @property
    def is_published(self) -> bool:
        return self.status_code == PUBLISHED

    @property
    def is_dead(self) -> bool:
        return self.status_code in (ERROR, EXPIRED)


class Permalink(PlatformModel):
    permalink: str = ""


class BusinessAccount(PlatformModel):
    id: str = ""
    username: str = ""
    name: str = ""
    profile_picture_url: str = ""


class Page(PlatformModel):
    id: str = ""
    access_token: str = ""
    instagram_business_account: BusinessAccount | None = None

    @property
    def is_linked(self) -> bool:
        return bool(self.access_token) and self.instagram_business_account is not None


class PageList(PlatformModel):
    data: list[Page] = []


class GranularScope(PlatformModel):
    target_ids: list[str] = []


class TokenInfo(PlatformModel):
    granular_scopes: list[GranularScope] = []
    user_id: str = ""


class DebugToken(PlatformModel):
    data: TokenInfo = TokenInfo()

from typing import Generic, TypeVar

from ..http import PlatformModel, Present

PROBLEM_PREFIX = "https://api.x.com/2/problems/"
PENDING = "pending"

T = TypeVar("T")


class Problem(PlatformModel):
    type: str = ""
    detail: str = ""
    title: str = ""
    message: str = ""

    @property
    def kind(self) -> str:
        return self.type.removeprefix(PROBLEM_PREFIX)

    @property
    def text(self) -> str:
        return self.detail or self.title or self.message


class ProblemAnswer(Problem):
    errors: list[Problem] = []
    data: dict | list | None = None

    @property
    def problem(self) -> Problem:
        if self.type or self.detail or self.title:
            return self
        if self.errors and not self.data:
            return self.errors[0]
        return Problem()


class Data(PlatformModel, Generic[T]):
    data: T


class Created(PlatformModel):
    id: Present


class User(PlatformModel):
    id: Present
    username: str = ""
    name: str = ""
    profile_image_url: str = ""


class ProcessingError(PlatformModel):
    message: str = ""
    name: str = ""

    @property
    def text(self) -> str:
        return self.message or self.name


class ProcessingInfo(PlatformModel):
    state: str = PENDING
    error: ProcessingError = ProcessingError()


class Media(PlatformModel):
    processing_info: ProcessingInfo | None = None


class MediaStatusAnswer(PlatformModel):
    data: Media = Media()

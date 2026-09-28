from typing import Annotated, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..errors import FailureType, PlatformError

MESSAGE_LIMIT = 500


class PlatformModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True, coerce_numbers_to_str=True)

    @model_validator(mode="before")
    @classmethod
    def _nulls_are_absent(cls, data):
        return {key: value for key, value in data.items() if value is not None} if isinstance(data, dict) else data


Present = Annotated[str, Field(min_length=1)]

M = TypeVar("M", bound=BaseModel)


class ResponseParser:
    def __init__(self, label: str):
        self.label = label

    def parse(self, response, model: type[M], *, refusal: str | None = None) -> M:
        try:
            body = response.json()
        except ValueError:
            body = None
        if body is None:
            raise self._refusal(refusal, "body")
        return self.parse_body(body, model, refusal=refusal)

    def parse_body(self, body, model: type[M], *, refusal: str | None = None) -> M:
        try:
            return model.model_validate(body)
        except ValidationError as error:
            details = self._field_paths(error)
        raise self._refusal(refusal, details)

    def _refusal(self, refusal: str | None, details: str) -> PlatformError:
        return PlatformError(
            FailureType.PLATFORM, refusal or f"{self.label} answered in an unexpected shape", details=details
        )

    @staticmethod
    def _field_paths(error: ValidationError) -> str:
        paths = (".".join(str(part) for part in detail["loc"]) or "body" for detail in error.errors())
        return ",".join(paths)[:MESSAGE_LIMIT]

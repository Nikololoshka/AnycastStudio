from typing import Annotated, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .failures import PLATFORM, PlatformFailure


class PlatformModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True, coerce_numbers_to_str=True)

    @model_validator(mode="before")
    @classmethod
    def _nulls_are_absent(cls, data):
        return {key: value for key, value in data.items() if value is not None} if isinstance(data, dict) else data


Present = Annotated[str, Field(min_length=1)]

M = TypeVar("M", bound=BaseModel)


def _field_paths(error: ValidationError) -> str:
    return ",".join(".".join(str(part) for part in detail["loc"]) or "body" for detail in error.errors())[:500]


def _refusal(label: str, refusal: str | None, details: str) -> PlatformFailure:
    return PlatformFailure(PLATFORM, refusal or f"{label} answered in an unexpected shape", details=details)


def parse_body(body, model: type[M], *, label: str, refusal: str | None = None) -> M:
    try:
        return model.model_validate(body)
    except ValidationError as error:
        details = _field_paths(error)
    raise _refusal(label, refusal, details)


def parse(response, model: type[M], *, label: str, refusal: str | None = None) -> M:
    try:
        body = response.json()
    except ValueError:
        body = None
    if body is None:
        raise _refusal(label, refusal, "body")
    return parse_body(body, model, label=label, refusal=refusal)

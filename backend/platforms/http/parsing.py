from typing import Annotated, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .failures import PLATFORM, PlatformFailure


class PlatformModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True, coerce_numbers_to_str=True)


Present = Annotated[str, Field(min_length=1)]

M = TypeVar("M", bound=BaseModel)


def _field_paths(error: ValidationError) -> str:
    return ",".join(".".join(str(part) for part in detail["loc"]) or "body" for detail in error.errors())[:500]


def parse(response, model: type[M], *, label: str, refusal: str | None = None) -> M:
    try:
        return model.model_validate(response.json())
    except ValueError as error:
        details = _field_paths(error) if isinstance(error, ValidationError) else "body"
    raise PlatformFailure(PLATFORM, refusal or f"{label} answered in an unexpected shape", details=details)

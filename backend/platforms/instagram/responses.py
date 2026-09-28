from ..core.http import PlatformModel, Present


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


class Created(PlatformModel):
    id: Present

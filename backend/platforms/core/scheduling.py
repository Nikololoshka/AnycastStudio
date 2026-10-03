from enum import StrEnum


class Scheduling(StrEnum):
    NATIVE = "native"
    STAGED_PUBLISH = "stagedPublish"
    DEFERRED_UPLOAD = "deferredUpload"
    UNSUPPORTED = "unsupported"

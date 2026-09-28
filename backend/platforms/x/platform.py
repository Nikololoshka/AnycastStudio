from ..core.config import PlatformConfig
from ..core.platform import Platform, PlatformFactory
from ..core.ports import Clock
from .auth import XProvider
from .client import LABEL, XClient
from .options import CAPABILITIES, XValidator
from .publish import MediaStatusApi, PostApi, XPublisher
from .upload import MediaUploadProtocol, XUploader


class XFactory(PlatformFactory):
    def build(self, config: PlatformConfig, clock: Clock) -> Platform:
        client = XClient(config.http)
        uploader = XUploader(MediaUploadProtocol(client), config.upload, clock)
        return Platform(
            name=XProvider.name,
            label=LABEL,
            capabilities=CAPABILITIES,
            provider=XProvider.create(config),
            publisher=XPublisher(uploader, MediaStatusApi(client), PostApi(client)),
            validator=XValidator(),
        )

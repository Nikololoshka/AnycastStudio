from ..core.config import PlatformConfig
from ..core.platform import Platform, PlatformFactory
from ..core.ports import Clock
from .auth import InstagramProvider
from .client import LABEL, InstagramClient
from .options import CAPABILITIES, InstagramValidator
from .publish import ContainerApi, InstagramPublisher
from .upload import ContainerUploadProtocol, InstagramUploader


class InstagramFactory(PlatformFactory):
    def build(self, config: PlatformConfig, clock: Clock) -> Platform:
        client = InstagramClient(config.http)
        containers = ContainerApi(client)
        uploader = InstagramUploader(ContainerUploadProtocol(client), containers, config.upload, clock)
        return Platform(
            name=InstagramProvider.name,
            label=LABEL,
            capabilities=CAPABILITIES,
            provider=InstagramProvider.create(config),
            publisher=InstagramPublisher(uploader, containers),
            validator=InstagramValidator(),
        )

from ...core.http import PlatformModel, Present


class InitData(PlatformModel):
    publish_id: Present
    upload_url: Present

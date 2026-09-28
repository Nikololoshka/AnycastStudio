from ...core.http import PlatformModel, Present


class User(PlatformModel):
    id: Present
    username: str = ""
    name: str = ""
    profile_image_url: str = ""

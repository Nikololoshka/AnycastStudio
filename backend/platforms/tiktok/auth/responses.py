from ...core.http import PlatformModel, Present


class User(PlatformModel):
    open_id: Present
    display_name: str = ""
    avatar_url: str = ""


class UserData(PlatformModel):
    user: User

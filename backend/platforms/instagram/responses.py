from ..http import PlatformModel, Present


class UserToken(PlatformModel):
    access_token: Present

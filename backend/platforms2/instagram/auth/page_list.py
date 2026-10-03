from ..instagram_answer import InstagramAnswer


class BusinessAccount(InstagramAnswer):
    id: str = ""
    username: str = ""
    name: str = ""
    profile_picture_url: str = ""


class Page(InstagramAnswer):
    id: str = ""
    access_token: str = ""
    instagram_business_account: BusinessAccount | None = None

    @property
    def is_linked(self) -> bool:
        return bool(self.access_token) and self.instagram_business_account is not None


class PageList(InstagramAnswer):
    data: list[Page] = []

    def linked(self) -> Page | None:
        return next((page for page in self.data if page.is_linked), None)

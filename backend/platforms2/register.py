from enum import Enum


class PLatformType(Enum):
    YouTube = "YouTube"
    Instagram = "Instagram"
    TikTok = "TikTok"
    X = "X"

def get_platform(platform: PLatformType):
    pass

def get_all_platforms() -> list:
    pass
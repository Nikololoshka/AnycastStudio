from pydantic import BaseModel, Field


class LoginSchema(BaseModel):
    # Plain string rather than EmailStr: a malformed address fails authentication
    # anyway, and reporting it as a format error would tell an attacker more.
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

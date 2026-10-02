from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    invite_token: str | None = None

class UserOut(UserBase):
    id: int

    class Config:
        from_attributes  = True

class BulkUserCreate(BaseModel):
    users: list[UserCreate]
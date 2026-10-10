from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    invite_token: str | None = None

class UserProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class AccountDeletionRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)

class AccountDeletionConfirmation(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")

class UserOut(UserBase):
    id: int

    class Config:
        from_attributes  = True

class BulkUserCreate(BaseModel):
    users: list[UserCreate]
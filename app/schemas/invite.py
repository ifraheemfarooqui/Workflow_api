from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Literal

class InviteCreate(BaseModel):
    email: EmailStr

class InviteOut(BaseModel):
    id: int
    team_id: int
    email: str
    token: str          # ← add this
    status: Literal["pending", "accepted", "revoked"]
    created_at: datetime

    class Config:
        from_attributes = True
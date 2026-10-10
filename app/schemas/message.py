from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MessageCreate(BaseModel):

    team_id: Optional[int] = None
    recipient_id: Optional[int] = None
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.team_id is None) == (self.recipient_id is None):
            raise ValueError("Provide exactly one of team_id or recipient_id")
        return self


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: Optional[int] = None
    team_id: Optional[int] = None
    recipient_id: Optional[int] = None
    content: str
    created_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
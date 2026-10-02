from pydantic import BaseModel, Field

class CommentBase(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class CommentCreate(CommentBase):
    task_id: int

class CommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class CommentOut(CommentBase):
    id: int
    task_id: int
    user_id: int

    class Config:
        from_attributes = True
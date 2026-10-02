from pydantic import BaseModel, Field, field_validator
from typing import Literal

class TaskBase(BaseModel):
    title: str = Field(max_length=100)
    description: str = ""
    status: Literal["todo", "in_progress", "done"] = "todo"
    priority: Literal["low", "medium", "high"] = "medium"
    project_id: int
    assigned_to: int | None = None

class CreateTask(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: Literal["todo", "in_progress", "done"] | None = None
    priority: Literal["low", "medium", "high"] | None = None
    project_id: int | None = None
    assigned_to: int | None = None

    @field_validator("title", "description", "status", "priority", "project_id")
    @classmethod
    def reject_null(cls, v):
        if v is None:
            raise ValueError("This field cannot be null")
        return v

class TaskOut(TaskBase):
    id:int

    class Config:
        from_attributes = True


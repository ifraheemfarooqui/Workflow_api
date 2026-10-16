from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    id: int
    team_id: int | None
    project_id: int | None
    task_id: int | None
    kind: str
    title: str
    body: str
    created_at: datetime
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

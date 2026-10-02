from pydantic import BaseModel
from app.schemas.team import TeamOut

class ProjectBase(BaseModel):
    name:str
    description:str = ""

class CreateProject(ProjectBase):
    team_id: int

class UpdateProject(BaseModel):
    name:str | None = None
    description:str | None = None

class ProjectOut(ProjectBase):
    id:int

    class Config:
        from_attributes = True

class ProjectTeamsOut(BaseModel):
    team:TeamOut

    class Config:
        from_attributes = True

class AddTeams(BaseModel):
    team_ids:list[int]

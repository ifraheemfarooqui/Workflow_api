from pydantic import BaseModel
from app.schemas.user import UserOut

class TeamBase(BaseModel):
    name:str

class TeamCreate(TeamBase):
    pass

class TeamUpdate(BaseModel):
    name: str | None=None

class TeamOut(TeamBase):
    id:int

    class Config:
        from_attributes= True

class TeamMemberOut(BaseModel):
    user:UserOut
    role_in_team :str

    class Config:
        from_attributes=True

class TeamWithMembers(TeamOut):
    members: list[TeamMemberOut] = []

class AddMembersRequest(BaseModel):
    user_ids: list[int]
    role_in_team: str = "member"
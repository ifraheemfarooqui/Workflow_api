from fastapi import Depends,HTTPException,status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from app.db.session import get_db
from app.core import security
from app.models.project_team import ProjectTeam
from app.models.project import Project
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.user import User
from app.models.task import Task

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
        token:str = Depends(oauth2_scheme),
        db:Session = Depends(get_db)
):
    creadentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},)
    try:
        payload = security.decode_access_token(token)
        # int() is inside the try now: a non-numeric "sub" is a 401, not a 500
        user_id = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise creadentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_deleted or payload.get("ver", 0) != user.token_version:
        raise creadentials_exception

    return user

def require_team_manager(team_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    membership = db.query(TeamMembership).filter_by(team_id=team_id, user_id=current_user.id).first()
    if not membership or membership.role_in_team != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a manager of this team can perform this action",
        )
    return current_user

def require_team_member(team_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    if not db.query(Team.id).filter(Team.id == team_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    membership = db.query(TeamMembership).filter_by(team_id=team_id, user_id=current_user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of this team to perform this action",
        )
    return current_user

def require_project_team_member(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    if not db.query(Project.id).filter(Project.id == project_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    is_member = (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(
            ProjectTeam.project_id == project_id,
            TeamMembership.user_id == current_user.id,
        )
        .first()
    )
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of this project's team to access it",
        )
    return current_user

def require_project_team_manager(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    is_manager = (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(
            ProjectTeam.project_id == project_id,
            TeamMembership.user_id == current_user.id,
            TeamMembership.role_in_team == "manager",
        )
        .first()
    )
    if not is_manager:
        raise HTTPException(status_code=403, detail="Only a manager of this project's team can perform this action")
    return current_user


def require_task_project_member(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> User:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    is_member = (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(
            ProjectTeam.project_id == task.project_id,
            TeamMembership.user_id == current_user.id,
        )
        .first()
    )
    if not is_member:
        raise HTTPException(status_code=403, detail="You must be a member of this task's project team to perform this action")
    return current_user
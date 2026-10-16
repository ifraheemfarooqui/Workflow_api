from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import (
    get_current_user,
    require_project_team_manager,
    require_project_team_member,
)
from app.models.user import User

from app.schemas.project import (
    CreateProject,
    ProjectTeamsOut,
    UpdateProject,
    ProjectOut,
    AddTeams
)

from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=ProjectOut)
def create_project(
    project_create: CreateProject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return project_service.create_project(db, project_create, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_team_member)
):
    db_project = project_service.get_project(db, project_id)

    if not db_project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return db_project


@router.get("/", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    return project_service.get_projects(db, current_user.id, skip, limit)

@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    project_update: UpdateProject,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_team_manager),   # was get_current_user
):
    db_project = project_service.update_project(db, project_id, project_update, current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_team_manager),
):
    db_project = project_service.delete_project(db, project_id, current_user.id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"detail": "Project removed"}


@router.post(
    "/{project_id}/teams",
    response_model=list[ProjectTeamsOut]
)
def add_teams(
    project_id: int,
    payload: AddTeams,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_team_manager)
):
    try:
        return project_service.add_teams_bulk(db, project_id, payload.team_ids, current_user.id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))


@router.delete("/{project_id}/teams/{team_id}")
def remove_team(
    project_id: int,
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_team_manager)
):
    try:
        removed_team = project_service.remove_team(db, project_id, team_id, current_user.id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))

    if not removed_team:
        raise HTTPException(
            status_code=404,
            detail="Team not found in the project"
        )

    return {"detail": "Team removed from the project"}


@router.get(
    "/{project_id}/teams",
    response_model=list[ProjectTeamsOut]
)
def list_project_teams(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_team_member)
):
    return project_service.get_project_teams(
        db,
        project_id
    )
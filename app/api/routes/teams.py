from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user, require_team_manager, require_team_member
from app.models.user import User

from app.schemas.team import (
    TeamUpdate,
    TeamCreate,
    TeamOut,
    TeamMemberOut,
    AddMembersRequest
)

from app.services import team_service


router = APIRouter(prefix="/teams", tags=["Teams"])


@router.post("/", response_model=TeamOut)
def create_team(
    team: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),   # any logged-in user, not require_roles
):
    return team_service.create_team(db, team, current_user.id)


@router.get("/{team_id}", response_model=TeamOut)
def read_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_member),
):
    db_team = team_service.get_team(db, team_id)

    if not db_team:
        raise HTTPException(status_code=404, detail="Team not found")

    return db_team


@router.get("/", response_model=list[TeamOut])
def list_team(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    return team_service.get_teams(db, current_user.id, skip, limit)


@router.put("/{team_id}", response_model=TeamOut)
def update_team(
    team_id: int,
    team_update: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager),
):
    db_team = team_service.update_team(db, team_id, team_update, current_user.id)

    if not db_team:
        raise HTTPException(status_code=404, detail="Team not found")

    return db_team


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager),
):
    db_team = team_service.delete_team(db, team_id, current_user.id)

    if not db_team:
        raise HTTPException(status_code=404, detail="Team not found")

    return {"detail": "Team removed successfully"}


@router.post("/{team_id}/members/{user_id}", response_model=TeamMemberOut)
def add_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager),
):
    membership = team_service.add_member(db, team_id, user_id, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )

    return membership


@router.post("/{team_id}/members", response_model=list[TeamMemberOut])
def add_members(
    team_id: int,
    payload: AddMembersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager)
):
    if not team_service.get_team(db, team_id):
        raise HTTPException(
            status_code=404,
            detail="Team not found"
        )
    return team_service.add_members_bulk(
        db,
        team_id,
        payload.user_ids,
        current_user.id,
        payload.role_in_team
    )


@router.delete("/{team_id}/members/{user_id}")
def delete_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager)
):
    if not team_service.get_team(db, team_id):
        raise HTTPException(status_code=404, detail="Team not found")

    membership = team_service.remove_member(db, team_id, user_id, current_user.id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    return {"detail": "User removed from team"}


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
def list_member(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_member)
):
    return team_service.get_team_members(db, team_id)

@router.post("/{team_id}/join", response_model=TeamMemberOut)
def join_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = team_service.join_team(db, team_id, current_user.id)
    if not membership:
        raise HTTPException(status_code=404, detail="Team not found")
    return membership
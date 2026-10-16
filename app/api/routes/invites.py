from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user, require_team_manager
from app.models.user import User
from app.schemas.invite import InviteCreate, InviteOut, PendingInviteOut
from app.services import invite_service

router = APIRouter(tags=["Invites"])


@router.get("/invites/mine", response_model=list[PendingInviteOut])
def list_my_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return invite_service.list_pending_invites(db, current_user.email)


@router.post("/teams/{team_id}/invites", response_model=InviteOut)
def create_invite(
    team_id: int,
    invite: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager),
):
    try:
        return invite_service.create_invite(db, team_id, invite, current_user.id)
    except invite_service.ExistingTeamMemberError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/teams/{team_id}/invites", response_model=list[InviteOut])
def list_team_invites(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_team_manager),
):
    return invite_service.list_team_invites(db, team_id)


@router.post("/invites/{token}/accept")
def accept_invite(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        invite_service.accept_invite(db, token, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": "Invite accepted, you've joined the team"}
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import BulkUserCreate, UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])

class BulkUserResponse(BaseModel):
    created: list[UserOut]
    skipped_emails: list[str]

@router.post("/",response_model=UserOut)
def register_user(user: UserCreate, db:Session = Depends(get_db)):
    return user_service.create_user(db,user)

@router.get("/{user_id}", response_model=UserOut)
def read_user(user_id:int,db:Session = Depends(get_db)):
    db_user = user_service.get_user(db,user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.post("/bulk", response_model=BulkUserResponse)
def register_users_bulk(payload: BulkUserCreate, db: Session = Depends(get_db)):
    created, skipped = user_service.create_users_bulk(db, payload.users)
    return BulkUserResponse(created=created, skipped_emails=skipped)

@router.get("/", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    return user_service.get_users(db, skip, limit)
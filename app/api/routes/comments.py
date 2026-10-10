from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentUpdate, CommentOut
from app.services import comment_service

router = APIRouter(prefix="/comments", tags=["Comments"])


@router.post("/", response_model=CommentOut, status_code=201)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return comment_service.create_comment(db, comment, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/", response_model=list[CommentOut])
def list_comments(
    skip: int = 0,
    limit: int = 10,
    task_id: int | None = None,
    user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return comment_service.list_comments(db, current_user.id, skip, limit, task_id, user_id)


@router.get("/{comment_id}", response_model=CommentOut)
def read_comment(comment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_comment = comment_service.get_comment(db, comment_id)
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if not comment_service.can_access_comment(db, db_comment, current_user.id):
        raise HTTPException(status_code=403, detail="You must be a member of this task's project team to access it")
    return db_comment


@router.put("/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_comment = comment_service.get_comment(db, comment_id)
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if not comment_service.is_owner_or_project_manager(db, db_comment, current_user.id):
        raise HTTPException(status_code=403, detail="You can only edit your own comments")

    return comment_service.update_comment(db, comment_id, comment_update)


@router.delete("/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_comment = comment_service.get_comment(db, comment_id)
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if not comment_service.is_owner_or_project_manager(db, db_comment, current_user.id):
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    return {"detail": "Comment deleted"} if comment_service.delete_comment(db, comment_id) else None
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Literal
from app.db.session import get_db
from app.api.deps import get_current_user, require_task_project_member
from app.models.user import User
from app.schemas.task import CreateTask, TaskUpdate, TaskOut
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=TaskOut, status_code=201)
def create_task(task: CreateTask, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return task_service.create_task(db, task, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/", response_model=list[TaskOut])
def list_tasks(
    skip: int = 0,
    limit: int = 10,
    project_id: int | None = None,
    assigned_to: int | None = None,
    status: Literal["todo", "in_progress", "done"] | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.list_tasks(db, current_user.id, skip, limit, project_id, assigned_to, status, priority)

@router.get("/{task_id}", response_model=TaskOut)
def read_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_task = task_service.get_task(db, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task_service._is_project_team_member(db, db_task.project_id, current_user.id):
        raise HTTPException(status_code=403, detail="You do not have access to this task")
    return db_task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_task_project_member),
):
    try:
        db_task = task_service.update_task(db, task_id, task_update, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_task_project_member)):
    db_task = task_service.delete_task(db, task_id, current_user.id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"detail": "Task deleted"}
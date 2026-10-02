from sqlalchemy.orm import Session
from app.models.project_team import ProjectTeam
from app.models.task import Task
from app.models.team_membership import TeamMembership
from app.schemas.task import CreateTask, TaskUpdate
from app.models.project import Project
from app.models.user import User


def _is_project_team_member(db: Session, project_id: int, user_id: int) -> bool:
    return (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(ProjectTeam.project_id == project_id, TeamMembership.user_id == user_id)
        .first()
        is not None
    )


def create_task(db: Session, task: CreateTask, creator_id: int):
    if not db.query(Project).filter(Project.id == task.project_id).first():
        raise ValueError("Project not found")

    if not _is_project_team_member(db, task.project_id, creator_id):
        raise PermissionError("You must be a member of this project's team to create a task")

    if task.assigned_to is not None:
        if not db.query(User).filter(User.id == task.assigned_to).first():
            raise ValueError("Assigned user not found")
        if not _is_project_team_member(db, task.project_id, task.assigned_to):
            raise ValueError("Assigned user is not a member of this project's team")

    db_task = Task(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task
def get_task(db:Session, task_id:int):
    return db.query(Task).filter(Task.id == task_id).first()

def update_task(db: Session, task_id: int, task: TaskUpdate):
    db_task = get_task(db, task_id)
    if not db_task:
        return None

    data = task.model_dump(exclude_unset=True)

    if data.get("project_id") is not None:
        if not db.query(Project).filter(Project.id == data["project_id"]).first():
            raise ValueError("Project not found")

    if data.get("assigned_to") is not None:
        project_id = data.get("project_id", db_task.project_id)
        if not db.query(User).filter(User.id == data["assigned_to"]).first():
            raise ValueError("Assigned user not found")
        if not _is_project_team_member(db, project_id, data["assigned_to"]):
            raise ValueError("Assigned user is not a member of this project's team")

    for key, value in data.items():
        setattr(db_task, key, value)

    db.commit()
    db.refresh(db_task)
    return db_task
def delete_task(db: Session, task_id: int):

    db_task = get_task(db, task_id)
    if not db_task:
        return None
    db.delete(db_task)
    db.commit()
    return db_task


def _user_project_ids(db: Session, user_id: int) -> list[int]:
    rows = (
        db.query(ProjectTeam.project_id)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(TeamMembership.user_id == user_id)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def list_tasks(
    db: Session,
    current_user_id: int,
    skip: int = 0,
    limit: int = 10,
    project_id: int | None = None,
    assigned_to: int | None = None,
    status: str | None = None,
    priority: str | None = None,
):
    accessible_ids = _user_project_ids(db, current_user_id)

    query = db.query(Task).filter(Task.project_id.in_(accessible_ids))

    if project_id is not None:
        query = query.filter(Task.project_id == project_id)
    if assigned_to is not None:
        query = query.filter(Task.assigned_to == assigned_to)
    if status is not None:
        query = query.filter(Task.status == status)
    if priority is not None:
        query = query.filter(Task.priority == priority)

    return query.order_by(Task.id).offset(skip).limit(limit).all()


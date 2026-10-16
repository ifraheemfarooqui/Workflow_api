from sqlalchemy.orm import Session
from app.models.project_team import ProjectTeam
from app.models.task import Task
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.schemas.task import CreateTask, TaskUpdate
from app.models.project import Project
from app.models.user import User
from app.services import notification_service


def _is_project_team_member(db: Session, project_id: int, user_id: int) -> bool:
    return (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(ProjectTeam.project_id == project_id, TeamMembership.user_id == user_id)
        .first()
        is not None
    )

def _display_task_value(db: Session, field: str, value):
    if field == "status":
        return {"todo": "To do", "in_progress": "In progress", "done": "Done"}.get(value, value)
    if field == "priority":
        return value.capitalize() if value else value
    if field == "assigned_to":
        user = db.query(User).filter(User.id == value).first() if value is not None else None
        return user.name if user else "Unassigned"
    if field == "assigned_team_id":
        team = db.query(Team).filter(Team.id == value).first() if value is not None else None
        return team.name if team else "Unassigned"
    if field == "project_id":
        project = db.query(Project).filter(Project.id == value).first() if value is not None else None
        return project.name if project else "Unknown project"
    if field == "description":
        return "updated"
    return value


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

    if task.assigned_team_id is not None:
        if not db.query(Team).filter(Team.id == task.assigned_team_id).first():
            raise ValueError("Assigned team not found")
        if not db.query(ProjectTeam).filter_by(
            project_id=task.project_id,
            team_id=task.assigned_team_id,
        ).first():
            raise ValueError("Assigned team is not linked to this project")

    db_task = Task(**task.model_dump())
    db.add(db_task)
    db.flush()
    notification_service.notify_project(
        db,
        task.project_id,
        creator_id,
        "task_created",
        "Task created",
        f"“{db_task.title}” was added. {notification_service.task_progress(db, task.project_id)}",
        task_id=db_task.id,
    )
    db.commit()
    db.refresh(db_task)
    return db_task
def get_task(db:Session, task_id:int):
    return db.query(Task).filter(Task.id == task_id).first()

def update_task(db: Session, task_id: int, task: TaskUpdate, actor_id: int):
    db_task = get_task(db, task_id)
    if not db_task:
        return None

    data = task.model_dump(exclude_unset=True)

    if data.get("project_id") is not None:
        if not db.query(Project).filter(Project.id == data["project_id"]).first():
            raise ValueError("Project not found")

    project_id = data.get("project_id", db_task.project_id)
    assigned_to = data.get("assigned_to", db_task.assigned_to)
    assigned_team_id = data.get("assigned_team_id", db_task.assigned_team_id)

    if assigned_to is not None:
        if not db.query(User).filter(User.id == assigned_to).first():
            raise ValueError("Assigned user not found")
        if not _is_project_team_member(db, project_id, assigned_to):
            raise ValueError("Assigned user is not a member of this project's team")

    if assigned_team_id is not None and not db.query(ProjectTeam).filter_by(
        project_id=project_id,
        team_id=assigned_team_id,
    ).first():
        raise ValueError("Assigned team is not linked to this project")

    field_names = {
        "assigned_team_id": "assigned team",
        "assigned_to": "assignee",
        "project_id": "project",
    }
    changes = [
        f"{field_names.get(key, key.replace('_', ' '))}: "
        f"{_display_task_value(db, key, getattr(db_task, key))} → "
        f"{_display_task_value(db, key, value)}"
        for key, value in data.items()
        if getattr(db_task, key) != value
    ]
    for key, value in data.items():
        setattr(db_task, key, value)

    if changes:
        db.flush()
        notification_service.notify_project(
            db,
            db_task.project_id,
            actor_id,
            "task_updated",
            "Task updated",
            f"“{db_task.title}”: {'; '.join(changes)}. {notification_service.task_progress(db, db_task.project_id)}",
            task_id=db_task.id,
        )
    db.commit()
    db.refresh(db_task)
    return db_task
def delete_task(db: Session, task_id: int, actor_id: int):

    db_task = get_task(db, task_id)
    if not db_task:
        return None
    project_id = db_task.project_id
    task_title = db_task.title
    db.delete(db_task)
    db.flush()
    notification_service.notify_project(
        db,
        project_id,
        actor_id,
        "task_deleted",
        "Task removed",
        f"“{task_title}” was removed. {notification_service.task_progress(db, project_id)}",
    )
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

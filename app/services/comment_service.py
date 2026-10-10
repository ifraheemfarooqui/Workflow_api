from sqlalchemy.orm import Session
from app.models.comment import Comment
from app.models.task import Task
from app.models.project_team import ProjectTeam
from app.models.team_membership import TeamMembership
from app.schemas.comment import CommentCreate, CommentUpdate


def _is_project_team_member(db: Session, project_id: int, user_id: int) -> bool:
    return (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(ProjectTeam.project_id == project_id, TeamMembership.user_id == user_id)
        .first()
        is not None
    )


def create_comment(db: Session, comment: CommentCreate, author_id: int):
    task = db.query(Task).filter(Task.id == comment.task_id).first()
    if not task:
        raise ValueError("Task not found")

    if not _is_project_team_member(db, task.project_id, author_id):
        raise PermissionError("You must be a member of this task's project team to comment")

    db_comment = Comment(content=comment.content, task_id=comment.task_id, user_id=author_id)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


def get_comment(db: Session, comment_id: int):
    return db.query(Comment).filter(Comment.id == comment_id).first()


def can_access_comment(db: Session, comment: Comment, user_id: int) -> bool:
    task = db.query(Task).filter(Task.id == comment.task_id).first()
    return task is not None and _is_project_team_member(db, task.project_id, user_id)


def list_comments(
    db: Session,
    current_user_id: int,
    skip: int = 0,
    limit: int = 10,
    task_id: int | None = None,
    user_id: int | None = None,
):
    query = (
        db.query(Comment)
        .join(Task, Task.id == Comment.task_id)
        .join(ProjectTeam, ProjectTeam.project_id == Task.project_id)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(TeamMembership.user_id == current_user_id)
    )
    if task_id is not None:
        query = query.filter(Comment.task_id == task_id)
    if user_id is not None:
        query = query.filter(Comment.user_id == user_id)
    return query.distinct().order_by(Comment.id).offset(skip).limit(limit).all()


def update_comment(db: Session, comment_id: int, comment_update: CommentUpdate):
    db_comment = get_comment(db, comment_id)
    if not db_comment:
        return None
    db_comment.content = comment_update.content
    db.commit()
    db.refresh(db_comment)
    return db_comment


def delete_comment(db: Session, comment_id: int):
    db_comment = get_comment(db, comment_id)
    if not db_comment:
        return None
    db.delete(db_comment)
    db.commit()
    return db_comment


def is_owner_or_project_manager(db: Session, comment: Comment, user_id: int) -> bool:
    task = db.query(Task).filter(Task.id == comment.task_id).first()
    if not task or not _is_project_team_member(db, task.project_id, user_id):
        return False
    if comment.user_id == user_id:
        return True
    return (
        db.query(ProjectTeam)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(
            ProjectTeam.project_id == task.project_id,
            TeamMembership.user_id == user_id,
            TeamMembership.role_in_team == "manager",
        )
        .first()
        is not None
    )
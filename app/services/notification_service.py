from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.project_team import ProjectTeam
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.task import Task


def _add_for_users(
    db: Session,
    user_ids: set[int],
    actor_id: int,
    kind: str,
    title: str,
    body: str,
    team_id: int | None = None,
    project_id: int | None = None,
    task_id: int | None = None,
) -> None:
    for user_id in user_ids - {actor_id}:
        db.add(Notification(
            user_id=user_id,
            actor_id=actor_id,
            team_id=team_id,
            project_id=project_id,
            task_id=task_id,
            kind=kind,
            title=title,
            body=body,
        ))


def notify_team(
    db: Session,
    team_id: int,
    actor_id: int,
    kind: str,
    title: str,
    body: str,
    project_id: int | None = None,
    task_id: int | None = None,
) -> None:
    user_ids = {
        row[0] for row in db.query(TeamMembership.user_id)
        .filter(TeamMembership.team_id == team_id)
        .all()
    }
    _add_for_users(db, user_ids, actor_id, kind, title, body, team_id, project_id, task_id)


def notify_project(
    db: Session,
    project_id: int,
    actor_id: int,
    kind: str,
    title: str,
    body: str,
    task_id: int | None = None,
) -> None:
    rows = (
        db.query(TeamMembership.user_id, TeamMembership.team_id)
        .join(ProjectTeam, ProjectTeam.team_id == TeamMembership.team_id)
        .filter(ProjectTeam.project_id == project_id)
        .all()
    )
    user_ids = {row.user_id for row in rows}
    team_id = rows[0].team_id if rows else None
    _add_for_users(db, user_ids, actor_id, kind, title, body, team_id, project_id, task_id)


def task_progress(db: Session, project_id: int) -> str:
    tasks = db.query(Task.status).filter(Task.project_id == project_id).all()
    total = len(tasks)
    complete = sum(status == "done" for (status,) in tasks)
    team_rows = (
        db.query(Team.id, Team.name)
        .join(ProjectTeam, ProjectTeam.team_id == Team.id)
        .filter(ProjectTeam.project_id == project_id)
        .distinct()
        .all()
    )
    team_summaries = []
    for team_id, team_name in team_rows:
        team_project_ids = select(ProjectTeam.project_id).where(ProjectTeam.team_id == team_id)
        team_tasks = db.query(Task.status).filter(Task.project_id.in_(team_project_ids)).all()
        team_complete = sum(status == "done" for (status,) in team_tasks)
        team_summaries.append(
            f"{team_name}: {team_complete}/{len(team_tasks)} tasks complete"
        )
    team_progress_text = f" Team progress: {'; '.join(team_summaries)}." if team_summaries else ""
    return f"Project progress: {complete}/{total} tasks complete.{team_progress_text}"


def list_notifications(db: Session, user_id: int, limit: int = 100):
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .all()
    )


def mark_read(db: Session, notification_id: int, user_id: int):
    notification = db.query(Notification).filter_by(
        id=notification_id,
        user_id=user_id,
    ).first()
    if notification is None:
        return None
    if notification.read_at is None:
        from datetime import datetime, timezone

        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: int) -> int:
    from datetime import datetime, timezone

    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .update({"read_at": datetime.now(timezone.utc)}, synchronize_session=False)
    )

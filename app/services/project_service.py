from sqlalchemy.orm import Session
from app.models.project_team import ProjectTeam
from app.models.task import Task
from app.models.team_membership import TeamMembership
from app.schemas.project import CreateProject,UpdateProject
from app.models.project import Project
from app.models.team import Team
from app.services import notification_service

def create_project(db: Session, project: CreateProject, creator_id: int):
    is_member = db.query(TeamMembership).filter_by(team_id=project.team_id, user_id=creator_id).first()
    if not is_member:
        raise PermissionError("You must be a member of this team to create a project under it")

    db_project = Project(name=project.name, description=project.description)
    db.add(db_project)
    db.flush()

    link = ProjectTeam(project_id=db_project.id, team_id=project.team_id)
    db.add(link)
    db.flush()
    notification_service.notify_team(
        db,
        project.team_id,
        creator_id,
        "project_created",
        "Project created",
        f"Project “{db_project.name}” was created.",
        project_id=db_project.id,
    )
    db.commit()
    db.refresh(db_project)

    return db_project

def get_project(db:Session,project_id:int):
    db_project = db.query(Project).filter(Project.id==project_id).first()
    if not db_project:
        return None
    return db_project

def update_project(db:Session,project_id: int,project_update:UpdateProject, actor_id: int):
    db_project = get_project(db,project_id)
    if not db_project:
        return None
    changes = []
    if project_update.name is not None:
        if db_project.name != project_update.name:
            changes.append("name changed")
        db_project.name=project_update.name
    if project_update.description is not None:
        if db_project.description != project_update.description:
            changes.append("description changed")
        db_project.description=project_update.description
    if changes:
        notification_service.notify_project(
            db,
            project_id,
            actor_id,
            "project_updated",
            "Project updated",
            f"Project “{db_project.name}” was updated ({', '.join(changes)}).",
        )
    db.commit()
    db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id:int, actor_id: int):
    db_project=get_project(db,project_id)
    if not db_project:
        return None
    notification_service.notify_project(
        db,
        project_id,
        actor_id,
        "project_deleted",
        "Project removed",
        f"Project “{db_project.name}” was removed.",
    )
    db.delete(db_project)
    db.commit()
    return db_project

def get_projects(db: Session, user_id: int, skip: int = 0, limit: int = 10):
    return (
        db.query(Project)
        .join(ProjectTeam, ProjectTeam.project_id == Project.id)
        .join(TeamMembership, TeamMembership.team_id == ProjectTeam.team_id)
        .filter(TeamMembership.user_id == user_id)
        .distinct()
        .order_by(Project.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_project_teams(db: Session, project_id: int):
    return db.query(ProjectTeam).filter_by(project_id=project_id).all()

def add_team(db: Session, project_id: int, team_id: int):
    existing = db.query(ProjectTeam).filter_by(project_id=project_id, team_id=team_id).first()
    if existing:
        return existing
    project_team = ProjectTeam(project_id=project_id, team_id=team_id)
    db.add(project_team)
    db.commit()
    db.refresh(project_team)
    return project_team

def add_teams_bulk(db: Session, project_id: int, team_ids: list[int], user_id: int):
    db_project = get_project(db, project_id)
    if not db_project:
        return None

    added = []
    for team_id in team_ids:
        is_manager = (
            db.query(TeamMembership.id)
            .filter(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
                TeamMembership.role_in_team == "manager",
            )
            .first()
        )
        if not is_manager:
            raise PermissionError("You must manage every team added to this project")
        existing = db.query(ProjectTeam).filter_by(project_id=project_id, team_id=team_id).first()
        if existing:
            continue
        project_team = ProjectTeam(project_id=project_id, team_id=team_id)
        db.add(project_team)
        added.append(project_team)

    if added:
        db.flush()
        added_names = [
            db.query(Team.name).filter(Team.id == project_team.team_id).scalar()
            for project_team in added
        ]
        notification_service.notify_project(
            db,
            project_id,
            user_id,
            "project_team_added",
            "Team added to project",
            f"{', '.join(name for name in added_names if name)} was added to project “{db_project.name}”.",
        )
    db.commit()
    for pt in added:
        db.refresh(pt)
    return added


def remove_team(db: Session, project_id: int, team_id: int, user_id: int):
    is_manager = (
        db.query(TeamMembership.id)
        .filter(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
            TeamMembership.role_in_team == "manager",
        )
        .first()
    )
    if not is_manager:
        raise PermissionError("You must manage this team to remove it from the project")
    project_team = db.query(ProjectTeam).filter_by(project_id=project_id, team_id=team_id).first()
    if not project_team:
        return None
    project = get_project(db, project_id)
    team = db.query(Team).filter(Team.id == team_id).first()
    if project and team:
        notification_service.notify_project(
            db,
            project_id,
            user_id,
            "project_team_removed",
            "Team removed from project",
            f"{team.name} was removed from project “{project.name}”.",
        )
    db.query(Task).filter_by(
        project_id=project_id,
        assigned_team_id=team_id,
    ).update({"assigned_team_id": None}, synchronize_session=False)
    db.delete(project_team)
    db.commit()
    return project_team

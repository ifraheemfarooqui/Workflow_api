from sqlalchemy.orm import Session
from app.models.project_team import ProjectTeam
from app.models.team_membership import TeamMembership
from app.schemas.project import CreateProject,UpdateProject
from app.models.project import Project

def create_project(db: Session, project: CreateProject, creator_id: int):
    is_member = db.query(TeamMembership).filter_by(team_id=project.team_id, user_id=creator_id).first()
    if not is_member:
        raise PermissionError("You must be a member of this team to create a project under it")

    db_project = Project(name=project.name, description=project.description)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    link = ProjectTeam(project_id=db_project.id, team_id=project.team_id)
    db.add(link)
    db.commit()

    return db_project

def get_project(db:Session,project_id:int):
    db_project = db.query(Project).filter(Project.id==project_id).first()
    if not db_project:
        return None
    return db_project

def update_project(db:Session,project_id: int,project_update:UpdateProject):
    db_project = get_project(db,project_id)
    if not db_project:
        return None
    if project_update.name is not None:
        db_project.name=project_update.name
    if project_update.description is not None:
        db_project.description=project_update.description
    db.commit()
    db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id:int):
    db_project=get_project(db,project_id)
    if not db_project:
        return None
    db.delete(db_project)
    db.commit()
    return db_project

def get_projects(db: Session, skip: int = 0, limit: int = 10):
    return db.query(Project).offset(skip).limit(limit).all()

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

def add_teams_bulk(db: Session, project_id: int, team_ids: list[int]):
    db_project = get_project(db, project_id)
    if not db_project:
        return None

    added = []
    for team_id in team_ids:
        existing = db.query(ProjectTeam).filter_by(project_id=project_id, team_id=team_id).first()
        if existing:
            continue
        project_team = ProjectTeam(project_id=project_id, team_id=team_id)
        db.add(project_team)
        added.append(project_team)

    db.commit()
    for pt in added:
        db.refresh(pt)
    return added


def remove_team(db: Session, project_id: int, team_id: int):
    project_team = db.query(ProjectTeam).filter_by(project_id=project_id, team_id=team_id).first()
    if not project_team:
        return None
    db.delete(project_team)
    db.commit()
    return project_team


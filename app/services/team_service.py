from sqlalchemy.orm import Session
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.schemas.team import TeamCreate, TeamUpdate

def create_team(db: Session, team: TeamCreate, creator_id: int):
    db_team = Team(name=team.name)
    db.add(db_team)
    db.commit()
    db.refresh(db_team)

    membership = TeamMembership(team_id=db_team.id, user_id=creator_id, role_in_team="manager")
    db.add(membership)
    db.commit()

    return db_team

def get_team(db:Session,team_id:int):
    return db.query(Team).filter(Team.id==team_id).first()

def get_teams(db:Session, skip:int=0,limit:int = 10):
    return db.query(Team).offset(skip).limit(limit).all()

def update_team(db: Session,team_id:int,team_update:TeamUpdate):
    db_team=get_team(db,team_id)
    if not db_team:
        return None
    if team_update.name is not None:
        db_team.name = team_update.name
    db.commit()
    db.refresh(db_team)
    return db_team

def delete_team(db:Session,team_id:int):
    db_team = get_team(db, team_id)
    if not db_team:
        return None
    db.delete(db_team)
    db.commit()
    return db_team

def add_member(db: Session, team_id: int, user_id: int, role_in_team: str = "member"):
    if not get_team(db, team_id):
        return None   # route turns this into a clean 404

    existing = db.query(TeamMembership).filter_by(team_id=team_id, user_id=user_id).first()
    if existing:
        return existing
    membership = TeamMembership(team_id=team_id, user_id=user_id, role_in_team=role_in_team)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership

def add_members_bulk(db: Session, team_id: int, user_ids: list[int], role_in_team: str = "member"):
    if not get_team(db, team_id):
        return None
    added = []
    for user_id in user_ids:
        existing = db.query(TeamMembership).filter_by(team_id=team_id, user_id=user_id).first()
        if existing:
            continue  # skip users already on the team
        membership = TeamMembership(team_id=team_id, user_id=user_id, role_in_team=role_in_team)
        db.add(membership)
        added.append(membership)
    db.commit()
    for m in added:
        db.refresh(m)
    return added

def remove_member(db:Session,team_id:int,user_id: int):
    if not get_team(db, team_id):
        return None
    membership = db.query(TeamMembership).filter_by(team_id=team_id,user_id=user_id).first()
    if not membership:
        return None
    db.delete(membership)
    db.commit()
    return membership

def get_team_members(db:Session,team_id:int):
    return db.query(TeamMembership).filter_by(team_id=team_id).all()

def join_team(db: Session, team_id: int, user_id: int):
    db_team = get_team(db, team_id)
    if not db_team:
        return None

    existing = db.query(TeamMembership).filter_by(team_id=team_id, user_id=user_id).first()
    if existing:
        return existing  # already a member, just return it, not an error

    membership = TeamMembership(team_id=team_id, user_id=user_id, role_in_team="member")
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership
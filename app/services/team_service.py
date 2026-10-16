from sqlalchemy.orm import Session
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.schemas.team import TeamCreate, TeamUpdate
from app.services import notification_service

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

def get_teams(db: Session, user_id: int, skip: int = 0, limit: int = 10):
    return (
        db.query(Team)
        .join(TeamMembership, TeamMembership.team_id == Team.id)
        .filter(TeamMembership.user_id == user_id)
        .order_by(Team.id)
        .offset(skip)
        .limit(limit)
        .all()
    )

def update_team(db: Session,team_id:int,team_update:TeamUpdate, actor_id: int):
    db_team=get_team(db,team_id)
    if not db_team:
        return None
    if team_update.name is not None:
        old_name = db_team.name
        db_team.name = team_update.name
        if old_name != db_team.name:
            notification_service.notify_team(
                db,
                team_id,
                actor_id,
                "team_updated",
                "Team renamed",
                f"Team “{old_name}” is now “{db_team.name}”.",
            )
    db.commit()
    db.refresh(db_team)
    return db_team

def delete_team(db:Session,team_id:int, actor_id: int):
    db_team = get_team(db, team_id)
    if not db_team:
        return None
    notification_service.notify_team(
        db,
        team_id,
        actor_id,
        "team_deleted",
        "Team removed",
        f"Team “{db_team.name}” was removed.",
    )
    db.delete(db_team)
    db.commit()
    return db_team

def add_member(db: Session, team_id: int, user_id: int, actor_id: int, role_in_team: str = "member"):
    if not get_team(db, team_id):
        return None   # route turns this into a clean 404

    existing = db.query(TeamMembership).filter_by(team_id=team_id, user_id=user_id).first()
    if existing:
        return existing
    membership = TeamMembership(team_id=team_id, user_id=user_id, role_in_team=role_in_team)
    db.add(membership)
    db.flush()
    notification_service.notify_team(
        db,
        team_id,
        actor_id,
        "member_added",
        "Team member added",
        f"A new member joined “{get_team(db, team_id).name}”.",
    )
    db.commit()
    db.refresh(membership)
    return membership

def add_members_bulk(
    db: Session,
    team_id: int,
    user_ids: list[int],
    actor_id: int,
    role_in_team: str = "member",
):
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
    if added:
        notification_service.notify_team(
            db,
            team_id,
            actor_id,
            "members_added",
            "Team members added",
            f"{len(added)} member{'s' if len(added) != 1 else ''} joined “{get_team(db, team_id).name}”.",
        )
    db.commit()
    for m in added:
        db.refresh(m)
    return added

def remove_member(db:Session,team_id:int,user_id: int, actor_id: int):
    if not get_team(db, team_id):
        return None
    membership = db.query(TeamMembership).filter_by(team_id=team_id,user_id=user_id).first()
    if not membership:
        return None
    notification_service.notify_team(
        db,
        team_id,
        actor_id,
        "member_removed",
        "Team member removed",
        f"A member was removed from “{get_team(db, team_id).name}”.",
    )
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
    db.flush()
    notification_service.notify_team(
        db,
        team_id,
        user_id,
        "member_joined",
        "New team member",
        f"A new member joined “{db_team.name}”.",
    )
    db.commit()
    db.refresh(membership)
    return membership
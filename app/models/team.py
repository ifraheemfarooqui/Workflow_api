# app/models/team.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    team_memberships = relationship(
        "TeamMembership",
        back_populates="team",
        cascade="all, delete-orphan"
    )
    project_teams = relationship(
        "ProjectTeam",
        back_populates="team",
        cascade="all, delete-orphan"
    )
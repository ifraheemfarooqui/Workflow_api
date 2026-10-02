# app/models/project_team.py
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class ProjectTeam(Base):
    __tablename__ = "project_teams"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    project = relationship("Project", back_populates="project_teams")
    team = relationship("Team", back_populates="project_teams")
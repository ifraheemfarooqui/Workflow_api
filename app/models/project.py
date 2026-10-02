# app/models/project.py
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    project_teams = relationship("ProjectTeam", back_populates="project",cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project",cascade="all, delete-orphan")
from sqlalchemy import String, Integer, ForeignKey, Column, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="todo")
    priority = Column(String(50), nullable=False, default="medium")

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)

    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")
    assigned_team = relationship("Team")
    comments = relationship("Comment", back_populates="task", cascade="all, delete-orphan")
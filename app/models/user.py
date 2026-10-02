# app/models/user.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)

    team_memberships = relationship("TeamMembership", back_populates="user")
    tasks = relationship("Task", back_populates="assignee")
    comments = relationship("Comment", back_populates="author")
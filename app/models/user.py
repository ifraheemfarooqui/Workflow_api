# app/models/user.py
from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="0")

    team_memberships = relationship("TeamMembership", back_populates="user")
    tasks = relationship("Task", back_populates="assignee")
    comments = relationship("Comment", back_populates="author")
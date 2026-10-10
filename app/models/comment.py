from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer,primary_key = True, index=True)
    content= Column(Text,nullable=False)

    user_id = Column(Integer,ForeignKey("users.id", ondelete="SET NULL"),nullable=True)
    task_id = Column(Integer,ForeignKey("tasks.id"),nullable=False)

    author = relationship("User",back_populates="comments")
    task = relationship("Task",back_populates="comments")
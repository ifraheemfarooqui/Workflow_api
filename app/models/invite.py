from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    email = Column(String(255), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending / accepted / revoked
    created_at = Column(DateTime, server_default=func.now())

    team = relationship("Team")
    inviter = relationship("User")
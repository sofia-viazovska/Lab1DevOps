from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

from .database import Base


class Task(Base):
    """Task Tracker entity (variant V3=2).

    Fields strictly per specification: id, title, status, created_at.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    status = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    """Payload for POST /tasks — per spec accepts only `title`."""

    title: str = Field(..., min_length=1, max_length=255)


class Task(BaseModel):
    """Full task representation returned by the API."""

    id: int
    title: str
    status: bool
    created_at: datetime

    class Config:
        from_attributes = True

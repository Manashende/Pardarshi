"""
Admin-managed topic taxonomy for the item bank — see app/models/topic.py
for why this exists as data rather than a hardcoded list: Pardarshi is
built to serve any exam board, not just one, so each deployment
configures its own subjects/topics here instead of a code change.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.api.deps import require_role
from app.models.user import User, UserRole
from app.models.topic import Topic

router = APIRouter(prefix="/topics", tags=["topics"])


class CreateTopicRequest(BaseModel):
    name: str = Field(..., min_length=1)


class TopicOut(BaseModel):
    id: str
    name: str


@router.post("", response_model=TopicOut)
def create_topic(
    req: CreateTopicRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "topic name cannot be blank")

    # Case-insensitive duplicate check — the entire point of this
    # feature is preventing exactly this kind of near-duplicate
    # ("Physics" vs "physics") from ever entering the approved list.
    existing = [t for t in db.query(Topic).all() if t.name.strip().lower() == name.lower()]
    if existing:
        raise HTTPException(400, f"a topic matching '{name}' already exists: '{existing[0].name}'")

    topic = Topic(name=name)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return TopicOut(id=str(topic.id), name=topic.name)


@router.get("", response_model=List[TopicOut])
def list_topics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(list(UserRole))),
):
    topics = db.query(Topic).order_by(Topic.name).all()
    return [TopicOut(id=str(t.id), name=t.name) for t in topics]
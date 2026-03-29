import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from shared.database import get_db_session
from shared.models import GatewayKey, ChatSession, ChatMessage
from api_gateway.auth import require_admin_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/chat", tags=["Chat Sessions"])


class SessionCreate(BaseModel):
    topic: Optional[str] = None


class MessageCreate(BaseModel):
    role: str
    content: str


@router.get("/sessions")
async def list_sessions(
    key: GatewayKey = Depends(require_admin_key),
    session: AsyncSession = Depends(get_db_session),
):
    """List all chat sessions, most recent first."""
    stmt = select(ChatSession).order_by(ChatSession.created_at.desc())
    result = await session.execute(stmt)
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "topic": s.topic,
            "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
        }
        for s in sessions
    ]


@router.post("/sessions")
async def create_session(
    req: SessionCreate,
    key: GatewayKey = Depends(require_admin_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new chat session."""
    db_session = ChatSession(id=uuid.uuid4(), topic=req.topic)
    session.add(db_session)
    await session.commit()
    await session.refresh(db_session)
    logger.info("Chat session created: id=%s topic=%s", db_session.id, req.topic)
    return {
        "id": str(db_session.id),
        "topic": db_session.topic,
        "created_at": db_session.created_at.isoformat() + "Z" if db_session.created_at else None,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    key: GatewayKey = Depends(require_admin_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Get a chat session with all its messages."""
    stmt = (
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": str(chat.id),
        "topic": chat.topic,
        "created_at": chat.created_at.isoformat() + "Z" if chat.created_at else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() + "Z" if m.created_at else None,
            }
            for m in (chat.messages or [])
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    key: GatewayKey = Depends(require_admin_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a chat session and all its messages."""
    stmt = delete(ChatSession).where(ChatSession.id == session_id)
    result = await session.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.commit()
    logger.info("Chat session deleted: id=%s", session_id)
    return {"status": "success"}


@router.delete("/sessions")
async def delete_all_sessions(
    key: GatewayKey = Depends(require_admin_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete all chat sessions."""
    await session.execute(delete(ChatSession))
    await session.commit()
    logger.info("All chat sessions deleted")
    return {"status": "success"}


@router.post("/sessions/{session_id}/messages")
async def add_message(
    session_id: uuid.UUID,
    req: MessageCreate,
    key: GatewayKey = Depends(require_admin_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Add a message to a chat session."""
    # Verify session exists
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    result = await session.execute(stmt)
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Session not found")

    msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role=req.role,
        content=req.content,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    logger.info("Chat message added: session=%s role=%s len=%d", session_id, req.role, len(req.content))

    return {
        "id": str(msg.id),
        "session_id": str(session_id),
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at.isoformat() + "Z" if msg.created_at else None,
    }

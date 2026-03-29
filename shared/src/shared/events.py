import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models import SystemEvent

logger = logging.getLogger(__name__)

async def log_event(
    session: AsyncSession,
    level: str,
    component: str,
    event_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an application event to the database.
    
    Args:
        session: An active SQLAlchemy AsyncSession. Note that this function does not commit the transaction, 
                 allowing callers to control transactional boundaries.
        level: Severity (e.g., 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        component: The logical module or service (e.g., 'selfheal', 'api-gateway', 'quota')
        event_type: A short string identifying the event (e.g., 'provider_down', 'quota_exceeded')
        message: Human-readable message
        details: Optional dictionary with extra context (must be JSON-serializable)
    """
    try:
        event = SystemEvent(
            level=level.upper(),
            component=component,
            event_type=event_type,
            message=message,
            details=details
        )
        session.add(event)
    except Exception as e:
        logger.error(f"Failed to log system event: {e}")

async def log_event_isolated(
    level: str,
    component: str,
    event_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an application event using a fresh, isolated database session.
    Use this when you want to ensure the log is committed immediately, 
    independent of any ongoing transaction or from a background task.
    """
    from shared.database import async_session_maker
    
    try:
        async with async_session_maker() as session:
            await log_event(session, level, component, event_type, message, details)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to log system event isolated: {e}")

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.message import Message, MessageRole


class MessageAgent:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_message(self, chat_id: int, role: MessageRole, content: str) -> Message:
        msg = Message(chat_id=chat_id, role=role, content=content)
        self._session.add(msg)
        await self._session.execute(
            update(Chat).where(Chat.id == chat_id).values(updated_at=func.now())
        )
        await self._session.flush()
        await self._session.refresh(msg)
        await self._session.commit()
        return msg

    async def get_history(
        self,
        chat_id: int,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        q = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
        if limit is not None:
            q = q.limit(limit).offset(offset)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def get_recent_for_prompt(self, chat_id: int, max_messages: int) -> list[Message]:
        """Last N messages in chronological order for LLM context."""
        result = await self._session.execute(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
        )
        rows = list(result.scalars().all())
        return list(reversed(rows))

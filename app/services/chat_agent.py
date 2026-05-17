from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.schemas.chat import ChatCreate


class ChatAgent:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: int, body: ChatCreate) -> Chat:
        raw_title = (body.title or "").strip()
        title = raw_title or "New chat"
        chat = Chat(user_id=user_id, title=title)
        self._session.add(chat)
        await self._session.flush()
        await self._session.refresh(chat)
        await self._session.commit()
        return chat

    async def list_for_user(self, user_id: int) -> list[Chat]:
        result = await self._session.execute(
            select(Chat).where(Chat.user_id == user_id).order_by(Chat.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned(self, user_id: int, chat_id: int) -> Chat | None:
        result = await self._session.execute(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, user_id: int, chat_id: int) -> bool:
        chat = await self.get_owned(user_id, chat_id)
        if not chat:
            return False
        await self._session.execute(delete(Chat).where(Chat.id == chat_id))
        await self._session.commit()
        return True

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserAgent:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_login(self, login: str) -> User | None:
        result = await self._session.execute(select(User).where(User.login == login))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_github_id(self, github_id: str) -> User | None:
        result = await self._session.execute(select(User).where(User.github_id == github_id))
        return result.scalar_one_or_none()

    async def create_user(self, login: str, password_hash: str) -> User:
        user = User(login=login, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        await self._session.commit()
        return user

    async def create_oauth_user(self, login: str, github_id: str) -> User:
        user = User(login=login, password_hash=None, github_id=github_id)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        await self._session.commit()
        return user

    async def link_github(self, user: User, github_id: str) -> User:
        user.github_id = github_id
        await self._session.commit()
        await self._session.refresh(user)
        return user

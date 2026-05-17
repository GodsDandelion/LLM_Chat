from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
MESSAGE_CACHE_TTL_SECONDS = 300


class CacheAgent:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def refresh_key(self, token: str) -> str:
        return f"refresh:{token}"

    def messages_key(self, chat_id: int) -> str:
        return f"chat:{chat_id}:messages"

    async def store_refresh(self, refresh_token: str, user_id: int) -> None:
        await self._redis.setex(self.refresh_key(refresh_token), REFRESH_TTL_SECONDS, str(user_id))

    async def get_refresh_user_id(self, refresh_token: str) -> int | None:
        raw = await self._redis.get(self.refresh_key(refresh_token))
        if raw is None:
            return None
        return int(raw)

    async def delete_refresh(self, refresh_token: str) -> None:
        await self._redis.delete(self.refresh_key(refresh_token))

    async def get_message_cache(self, chat_id: int) -> list[dict[str, Any]] | None:
        raw = await self._redis.get(self.messages_key(chat_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return None
        return None

    async def set_message_cache(self, chat_id: int, messages: list[dict[str, Any]]) -> None:
        await self._redis.setex(
            self.messages_key(chat_id),
            MESSAGE_CACHE_TTL_SECONDS,
            json.dumps(messages),
        )

    async def invalidate_message_cache(self, chat_id: int) -> None:
        await self._redis.delete(self.messages_key(chat_id))

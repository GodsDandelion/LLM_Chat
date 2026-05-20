from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Optional, Union

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.message import MessageRole
from app.schemas.message import MessageOut, SendMessageResponse
from app.services.cache_agent import CacheAgent
from app.services.chat_agent import ChatAgent
from app.services.llm_agent import LLMAgent, trim_assistant_reply
from app.services.message_agent import MessageAgent


def _next_stream_chunk(iterator: object) -> str | None:
    try:
        return next(iterator)  # type: ignore[arg-type]
    except StopIteration:
        return None


class ChatService:
    def __init__(self, session: AsyncSession, cache: CacheAgent) -> None:
        self._session = session
        self._cache = cache

    async def get_messages(
        self,
        *,
        user_id: int,
        chat_id: int,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[MessageOut]:
        chats = ChatAgent(self._session)
        if not await chats.get_owned(user_id, chat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        if limit is None and offset == 0:
            try:
                cached = await self._cache.get_message_cache(chat_id)
                if cached is not None:
                    return [MessageOut.model_validate(row) for row in cached]
            except Exception:  # noqa: BLE001 — cache must not block history load
                pass

        messages = await MessageAgent(self._session).get_history(chat_id, limit=limit, offset=offset)
        out = [MessageOut.model_validate(m) for m in messages]
        if limit is None and offset == 0 and out:
            try:
                await self._cache.set_message_cache(chat_id, [m.model_dump(mode="json") for m in out])
            except Exception:  # noqa: BLE001
                pass
        return out

    async def send_message(
        self,
        *,
        user_id: int,
        chat_id: int,
        content: str,
        stream: bool,
    ) -> Union[SendMessageResponse, StreamingResponse]:
        chats = ChatAgent(self._session)
        if not await chats.get_owned(user_id, chat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

        await self._cache.invalidate_message_cache(chat_id)
        messages = MessageAgent(self._session)
        user_msg = await messages.add_message(chat_id, MessageRole.user, content)

        settings = get_settings()
        recent = await messages.get_recent_for_prompt(chat_id, settings.llm_context_messages)
        if not recent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No messages")
        last = recent[-1]
        if last.role != MessageRole.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Last message must be from user",
            )
        prior = recent[:-1]
        history = [(m.role.value, m.content) for m in prior]
        user_text = last.content
        llm = LLMAgent.get()

        if stream:

            async def sse() -> AsyncIterator[bytes]:
                loop = asyncio.get_running_loop()
                iterator = llm.stream_generate(history, user_text)
                parts: list[str] = []
                try:
                    while True:
                        chunk = await loop.run_in_executor(None, _next_stream_chunk, iterator)
                        if chunk is None:
                            break
                        parts.append(chunk)
                        yield f"data: {json.dumps({'text': chunk})}\n\n".encode()
                    assistant_text = trim_assistant_reply("".join(parts)) or "."
                    await messages.add_message(chat_id, MessageRole.assistant, assistant_text)
                    await self._cache.invalidate_message_cache(chat_id)
                    yield b"data: [DONE]\n\n"
                except Exception as exc:  # noqa: BLE001
                    yield f"data: {json.dumps({'error': str(exc)})}\n\n".encode()

            return StreamingResponse(sse(), media_type="text/event-stream")

        try:
            assistant_text = llm.generate(history, user_text)
        except (FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        assistant_msg = await messages.add_message(chat_id, MessageRole.assistant, assistant_text)
        await self._cache.invalidate_message_cache(chat_id)
        return SendMessageResponse(
            user_message=MessageOut.model_validate(user_msg),
            assistant_message=MessageOut.model_validate(assistant_msg),
        )


from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_cache_agent, get_current_user
from app.models.message import MessageRole
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatOut
from app.schemas.message import MessageCreate, MessageOut
from app.services.cache_agent import CacheAgent
from app.services.chat_agent import ChatAgent
from app.services.llm_agent import LLMAgent, trim_assistant_reply
from app.services.message_agent import MessageAgent

router = APIRouter()


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


def _next_stream_chunk(iterator: object) -> str | None:
    try:
        return next(iterator)  # type: ignore[arg-type]
    except StopIteration:
        return None


def _history_and_last_user(recent: list) -> tuple[list[tuple[str, str]], str]:
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
    return history, last.content


@router.get("", response_model=list[ChatOut])
async def list_chats(
    current: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
) -> list[ChatOut]:
    chats = await ChatAgent(session).list_for_user(current.id)
    return [ChatOut.model_validate(c) for c in chats]


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: ChatCreate,
    current: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
) -> ChatOut:
    chat = await ChatAgent(session).create(current.id, body)
    return ChatOut.model_validate(chat)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    current: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
) -> Response:
    ok = await ChatAgent(session).delete(current.id, chat_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    await cache.invalidate_message_cache(chat_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(
    chat_id: int,
    current: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
    limit: Optional[int] = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[MessageOut]:
    chats = ChatAgent(session)
    if not await chats.get_owned(current.id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    if limit is None and offset == 0:
        try:
            cached = await cache.get_message_cache(chat_id)
            if cached is not None:
                return [MessageOut.model_validate(row) for row in cached]
        except Exception:  # noqa: BLE001 — cache must not block history load
            pass

    messages = await MessageAgent(session).get_history(chat_id, limit=limit, offset=offset)
    out = [MessageOut.model_validate(m) for m in messages]
    if limit is None and offset == 0 and out:
        try:
            await cache.set_message_cache(chat_id, [m.model_dump(mode="json") for m in out])
        except Exception:  # noqa: BLE001
            pass
    return out


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: int,
    body: MessageCreate,
    current: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
    stream: bool = Query(default=False),
):
    chats = ChatAgent(session)
    if not await chats.get_owned(current.id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    await cache.invalidate_message_cache(chat_id)
    messages = MessageAgent(session)
    user_msg = await messages.add_message(chat_id, MessageRole.user, body.content)

    settings = get_settings()
    recent = await messages.get_recent_for_prompt(chat_id, settings.llm_context_messages)
    history, user_text = _history_and_last_user(recent)
    llm = LLMAgent.get()

    if stream:

        async def sse() -> AsyncIterator[bytes]:
            loop = asyncio.get_event_loop()
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
                await cache.invalidate_message_cache(chat_id)
                yield b"data: [DONE]\n\n"
            except Exception as exc:  # noqa: BLE001
                yield f"data: {json.dumps({'error': str(exc)})}\n\n".encode()

        return StreamingResponse(sse(), media_type="text/event-stream")

    try:
        assistant_text = llm.generate(history, user_text)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    assistant_msg = await messages.add_message(chat_id, MessageRole.assistant, assistant_text)
    await cache.invalidate_message_cache(chat_id)
    return SendMessageResponse(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg),
    )

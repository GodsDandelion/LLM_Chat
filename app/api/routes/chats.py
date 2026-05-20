from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_cache_agent, get_current_user
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatOut
from app.schemas.message import MessageCreate, MessageOut, SendMessageResponse
from app.services.cache_agent import CacheAgent
from app.services.chat_agent import ChatAgent
from app.services.chat_service import ChatService

router = APIRouter()


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
    return await ChatService(session, cache).get_messages(
        user_id=current.id,
        chat_id=chat_id,
        limit=limit,
        offset=offset,
    )


@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(
    chat_id: int,
    body: MessageCreate,
    current: Annotated[User, Depends(get_current_user)],
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
    stream: bool = Query(default=False),
):
    return await ChatService(session, cache).send_message(
        user_id=current.id,
        chat_id=chat_id,
        content=body.content,
        stream=stream,
    )

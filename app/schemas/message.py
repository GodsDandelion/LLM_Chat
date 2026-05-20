from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import MessageRole


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    role: MessageRole
    content: str
    created_at: datetime


class SendMessageResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut

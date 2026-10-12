"""Conversation and message API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ChatSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    chats: list[ChatSummary]


class ChatDetail(ChatSummary):
    pass


class MessageCreate(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    document_ids: list[uuid.UUID] | None = None
    top_k: int = Field(5, ge=1, le=20)


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    status: str
    sources: list[dict] | None = None
    created_at: datetime
    token_input: int | None = None
    token_output: int | None = None


class MessageListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    messages: list[MessageOut]

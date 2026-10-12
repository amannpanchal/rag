"""Conversation and message lifecycle with ownership checks."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.conversation_models import Conversation, ConversationSummary, Message
from app.db.postgres import get_db_session
from app.schemas.chat import (
    ChatDetail,
    ChatListResponse,
    ChatSummary,
    MessageListResponse,
    MessageOut,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _message_out(row: Message) -> MessageOut:
    sources = None
    if row.sources_json:
        try:
            sources = json.loads(row.sources_json)
        except json.JSONDecodeError:
            sources = None
    return MessageOut(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        status=row.status,
        sources=sources,
        created_at=row.created_at,
        token_input=row.token_input,
        token_output=row.token_output,
    )


async def _owned_conversation(session, chat_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    result = await session.execute(
        select(Conversation).where(Conversation.id == chat_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        exists = await session.execute(select(Conversation.id).where(Conversation.id == chat_id))
        if exists.scalar_one_or_none() is not None:
            raise NotFoundError("Conversation not found")
        raise NotFoundError("Conversation not found")
    return conv


async def create_conversation(user_id: uuid.UUID, title: str | None = None) -> ChatDetail:
    async with get_db_session() as session:
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=(title or "New chat").strip() or "New chat",
        )
        session.add(conv)
        await session.flush()
        return ChatDetail(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )


async def list_conversations(user_id: uuid.UUID, page: int = 1, limit: int = 20) -> ChatListResponse:
    offset = (page - 1) * limit
    async with get_db_session() as session:
        count_q = select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        total = (await session.execute(count_q)).scalar_one()
        rows = (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
        chats: list[ChatSummary] = []
        for conv in rows:
            msg_count = (
                await session.execute(
                    select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
                )
            ).scalar_one()
            chats.append(
                ChatSummary(
                    id=conv.id,
                    title=conv.title,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    message_count=msg_count,
                )
            )
    pages = max(1, math.ceil(total / limit)) if total else 1
    return ChatListResponse(total=total, page=page, limit=limit, pages=pages, chats=chats)


async def get_conversation(chat_id: uuid.UUID, user_id: uuid.UUID) -> ChatDetail:
    async with get_db_session() as session:
        conv = await _owned_conversation(session, chat_id, user_id)
        msg_count = (
            await session.execute(
                select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)
            )
        ).scalar_one()
        return ChatDetail(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count,
        )


async def rename_conversation(chat_id: uuid.UUID, user_id: uuid.UUID, title: str) -> ChatDetail:
    async with get_db_session() as session:
        conv = await _owned_conversation(session, chat_id, user_id)
        conv.title = title.strip()
        conv.updated_at = datetime.now(tz=timezone.utc)
        await session.flush()
        return ChatDetail(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )


async def delete_conversation(chat_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with get_db_session() as session:
        await _owned_conversation(session, chat_id, user_id)
        await session.execute(delete(Conversation).where(Conversation.id == chat_id))


async def list_messages(
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int = 1,
    limit: int = 50,
) -> MessageListResponse:
    offset = (page - 1) * limit
    async with get_db_session() as session:
        await _owned_conversation(session, chat_id, user_id)
        total = (
            await session.execute(
                select(func.count()).select_from(Message).where(Message.conversation_id == chat_id)
            )
        ).scalar_one()
        rows = (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == chat_id)
                .order_by(Message.created_at.asc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
    pages = max(1, math.ceil(total / limit)) if total else 1
    return MessageListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        messages=[_message_out(row) for row in rows],
    )


async def delete_message(chat_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID) -> None:
    async with get_db_session() as session:
        await _owned_conversation(session, chat_id, user_id)
        result = await session.execute(
            select(Message).where(Message.id == message_id, Message.conversation_id == chat_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            raise NotFoundError("Message not found")
        await session.execute(delete(Message).where(Message.id == message_id))
        summary = (
            await session.execute(
                select(ConversationSummary).where(ConversationSummary.conversation_id == chat_id)
            )
        ).scalar_one_or_none()
        if summary is not None:
            await session.execute(
                delete(ConversationSummary).where(ConversationSummary.conversation_id == chat_id)
            )


async def get_or_create_conversation(
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID,
) -> uuid.UUID:
    async with get_db_session() as session:
        if conversation_id is not None:
            result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
            existing = result.scalar_one_or_none()
            if existing is not None:
                if user_id is None or existing.user_id != user_id:
                    raise NotFoundError("Conversation not found")
                return existing.id
        new_conv = Conversation(id=uuid.uuid4(), user_id=user_id, title="New chat")
        session.add(new_conv)
        await session.flush()
        return new_conv.id


async def load_history(
    conversation_id: uuid.UUID,
    max_pairs: int | None = None,
) -> list[BaseMessage]:
    settings = get_settings()
    max_pairs = max_pairs if max_pairs is not None else settings.MAX_HISTORY_PAIRS
    async with get_db_session() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_pairs * 2)
        )
        rows = list(reversed(result.scalars().all()))

    messages: list[BaseMessage] = []
    for row in rows:
        if row.role == "user":
            messages.append(HumanMessage(content=row.content))
        elif row.role == "assistant":
            messages.append(AIMessage(content=row.content))
    return messages


async def load_recent_messages(conversation_id: uuid.UUID, limit: int = 40) -> list[Message]:
    async with get_db_session() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))


async def get_summary(conversation_id: uuid.UUID) -> ConversationSummary | None:
    async with get_db_session() as session:
        result = await session.execute(
            select(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id)
        )
        return result.scalar_one_or_none()


async def upsert_summary(
    conversation_id: uuid.UUID,
    summary_text: str,
    covered_until_message_id: uuid.UUID | None,
) -> None:
    now = datetime.now(tz=timezone.utc)
    async with get_db_session() as session:
        result = await session.execute(
            select(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            session.add(
                ConversationSummary(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    summary_text=summary_text,
                    covered_until_message_id=covered_until_message_id,
                    updated_at=now,
                )
            )
        else:
            row.summary_text = summary_text
            row.covered_until_message_id = covered_until_message_id
            row.updated_at = now


async def maybe_set_title(conversation_id: uuid.UUID, user_text: str) -> None:
    snippet = user_text.strip().replace("\n", " ")[:80]
    if not snippet:
        return
    async with get_db_session() as session:
        result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv is not None and conv.title in ("New chat", ""):
            conv.title = snippet
            conv.updated_at = datetime.now(tz=timezone.utc)


async def save_user_message(conversation_id: uuid.UUID, content: str) -> Message:
    now = datetime.now(tz=timezone.utc)
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=content,
        status="completed",
        created_at=now,
    )
    async with get_db_session() as session:
        conv = (await session.execute(select(Conversation).where(Conversation.id == conversation_id))).scalar_one_or_none()
        if conv is not None:
            conv.updated_at = now
        session.add(msg)
        await session.flush()
        await session.refresh(msg)
        return msg


async def save_assistant_message(
    conversation_id: uuid.UUID,
    content: str,
    status: str = "completed",
    sources: list[dict] | None = None,
    token_input: int | None = None,
    token_output: int | None = None,
) -> Message:
    now = datetime.now(tz=timezone.utc)
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        status=status,
        sources_json=json.dumps(sources) if sources else None,
        token_input=token_input,
        token_output=token_output,
        created_at=now,
    )
    async with get_db_session() as session:
        conv = (await session.execute(select(Conversation).where(Conversation.id == conversation_id))).scalar_one_or_none()
        if conv is not None:
            conv.updated_at = now
        session.add(msg)
        await session.flush()
        await session.refresh(msg)
        return msg


async def save_turn(
    conversation_id: uuid.UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    await save_user_message(conversation_id, user_message)
    await save_assistant_message(conversation_id, assistant_message)


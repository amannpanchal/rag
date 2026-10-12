"""User scoped conversation history API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.user_models import User
from app.schemas.chat import ChatCreate, ChatDetail, ChatListResponse, ChatUpdate, MessageListResponse
from app.services import conversation_service as conversations

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail="Conversation not found")


@router.post("", response_model=ChatDetail, status_code=status.HTTP_201_CREATED)
async def create_chat(payload: ChatCreate, user: User = Depends(get_current_user)) -> ChatDetail:
    return await conversations.create_conversation(user.id, payload.title)


@router.get("", response_model=ChatListResponse)
async def list_chats(
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(get_current_user),
) -> ChatListResponse:
    return await conversations.list_conversations(user.id, page, limit)


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: uuid.UUID, user: User = Depends(get_current_user)) -> ChatDetail:
    try:
        return await conversations.get_conversation(chat_id, user.id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def list_chat_messages(
    chat_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: User = Depends(get_current_user),
) -> MessageListResponse:
    try:
        return await conversations.list_messages(chat_id, user.id, page, limit)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/{chat_id}", response_model=ChatDetail)
async def rename_chat(chat_id: uuid.UUID, payload: ChatUpdate, user: User = Depends(get_current_user)) -> ChatDetail:
    try:
        return await conversations.rename_conversation(chat_id, user.id, payload.title)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(chat_id: uuid.UUID, user: User = Depends(get_current_user)) -> None:
    try:
        await conversations.delete_conversation(chat_id, user.id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/{chat_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_message(chat_id: uuid.UUID, message_id: uuid.UUID, user: User = Depends(get_current_user)) -> None:
    try:
        await conversations.delete_message(chat_id, message_id, user.id)
    except NotFoundError as exc:
        raise _not_found(exc) from exc

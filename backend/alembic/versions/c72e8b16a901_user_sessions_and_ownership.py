"""Add user sessions and ownership fields.

Revision ID: c72e8b16a901
Revises: b35f99144db8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c72e8b16a901"
down_revision: Union[str, None] = "b35f99144db8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(320), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    tables = _tables()
    if "sessions" not in tables:
        op.create_table(
            "sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
        op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])
        op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    tables = _tables()
    if "documents" in tables:
        cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("documents")}
        if "user_id" not in cols:
            op.add_column("documents", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        # Existing ownerless documents stay quarantined (NULL owner).
        indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("documents")}
        if "ix_documents_user_id" not in indexes:
            op.create_index("ix_documents_user_id", "documents", ["user_id"])
        document_fks = sa.inspect(op.get_bind()).get_foreign_keys("documents")
        has_owner_fk = any(fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in document_fks)
        if not has_owner_fk:
            op.create_foreign_key("fk_documents_user_id_users", "documents", "users", ["user_id"], ["id"], ondelete="CASCADE")
        uniques = {c["name"] for c in sa.inspect(op.get_bind()).get_unique_constraints("documents")}
        if "uq_documents_user_hash" not in uniques:
            op.create_unique_constraint("uq_documents_user_hash", "documents", ["user_id", "file_hash"])

    tables = _tables()
    if "conversations" in tables:
        cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("conversations")}
        if "user_id" not in cols:
            op.add_column("conversations", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("conversations")}
        if "ix_conversations_user_id" not in indexes:
            op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
        conversation_fks = sa.inspect(op.get_bind()).get_foreign_keys("conversations")
        has_owner_fk = any(fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in conversation_fks)
        if not has_owner_fk:
            op.create_foreign_key("fk_conversations_user_id_users", "conversations", "users", ["user_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    # Ownership data may have been written after upgrade; retain it on downgrade.
    pass


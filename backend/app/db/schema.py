"""Additive schema bootstrap for existing PostgreSQL databases."""

from sqlalchemy import text

from app.utils.logging import get_logger

logger = get_logger(__name__)

_ALTER_STATEMENTS = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id UUID",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id UUID",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title VARCHAR(255) DEFAULT 'New chat'",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'completed'",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS sources_json TEXT",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS token_input INTEGER",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS token_output INTEGER",
    "ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_file_hash_key",
    """
    DO $$ BEGIN
        ALTER TABLE documents
            ADD CONSTRAINT uq_documents_user_hash UNIQUE (user_id, file_hash);
    EXCEPTION
        WHEN duplicate_object THEN NULL;
        WHEN unique_violation THEN NULL;
    END $$
    """,
    "CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id)",
]


async def apply_additive_schema(engine) -> None:
    """Apply IF NOT EXISTS column/index changes that create_all cannot do."""
    async with engine.begin() as conn:
        for stmt in _ALTER_STATEMENTS:
            try:
                await conn.execute(text(stmt))
            except Exception as exc:
                logger.warning("Schema bootstrap statement skipped: %s", exc)
    logger.info("Additive PostgreSQL schema verified")

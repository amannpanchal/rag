"""
Qdrant vector store operations.

Responsibilities:
  - Ensure the collection exists with the correct vector configuration.
  - Upsert document chunk vectors with rich payload for retrieval.
  - Provide a clean delete-by-document-id helper for future use.
"""

import uuid
from dataclasses import dataclass

from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.db.qdrant import get_qdrant_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

NAMESPACE_RAG = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def generate_point_id(
    filename: str, page_number: int, section: str | None, heading: str | None, chunk_index: int, text: str, user_id: str | None = None
) -> str:
    """Generate a deterministic UUID for a chunk based on its content and metadata."""
    stable_name = f"{user_id or 'legacy'}::{filename}::{page_number}::{section}::{heading}::{chunk_index}::{text}"
    return str(uuid.uuid5(NAMESPACE_RAG, stable_name))



@dataclass
class VectorPoint:
    """A single vector + payload to be upserted into Qdrant."""

    vector: list[float]
    document_id: str           # UUID string of the parent Document row
    user_id: str
    filename: str
    chunk_index: int
    page_number: int
    text: str
    heading: str | None = None
    section: str | None = None


async def ensure_collection() -> None:
    """
    Create the Qdrant collection if it does not already exist.
    Safe to call on every startup ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â idempotent.
    """
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION

    existing = await client.get_collections()
    names = {c.name for c in existing.collections}

    if collection_name in names:
        logger.debug("Qdrant collection '%s' already exists", collection_name)
        await client.create_payload_index(collection_name=collection_name, field_name="user_id", field_schema=qmodels.PayloadSchemaType.KEYWORD)
        return

    await client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIMENSION,
            distance=qmodels.Distance.COSINE,
        ),
        # Optimiser settings tuned for read-heavy RAG workloads
        optimizers_config=qmodels.OptimizersConfigDiff(
            indexing_threshold=20_000,
        ),
        # Payload index for fast filtered retrieval by document_id
        on_disk_payload=True,
    )

    # Create a payload index on document_id for fast per-document filtering
    await client.create_payload_index(
        collection_name=collection_name,
        field_name="document_id",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    await client.create_payload_index(collection_name=collection_name, field_name="user_id", field_schema=qmodels.PayloadSchemaType.KEYWORD)

    logger.info(
        "Created Qdrant collection '%s' (dim=%d, distance=COSINE)",
        collection_name,
        settings.EMBEDDING_DIMENSION,
    )


async def upsert_vectors(points: list[VectorPoint]) -> int:
    """
    Upsert a batch of vectors into the Qdrant collection.

    Each point receives a random UUID as its Qdrant point ID.
    The ``document_id`` field in the payload is the PostgreSQL row UUID
    and is the join key for cross-store lookups.

    Returns:
        Number of points upserted.
    """
    if not points:
        return 0

    settings = get_settings()
    client = get_qdrant_client()

    qdrant_points = []

    for p in points:
        deterministic_id = generate_point_id(
            p.filename, p.page_number, p.section, p.heading, p.chunk_index, p.text, p.user_id
        )

        qdrant_points.append(
            qmodels.PointStruct(
                id=deterministic_id,
                vector=p.vector,
                payload={
                    "document_id": p.document_id,
                    "user_id": p.user_id,
                    "filename": p.filename,
                    "chunk_index": p.chunk_index,
                    "page_number": p.page_number,
                    "text": p.text,
                    "char_count": len(p.text),
                    "heading": p.heading,
                    "section": p.section,
                },
            )
        )

    await client.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=qdrant_points,
        wait=True,          # wait for WAL flush ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â guarantees durability
    )

    logger.info(
        "Upserted %d vectors into '%s'",
        len(qdrant_points),
        settings.QDRANT_COLLECTION,
    )
    return len(qdrant_points)


async def delete_by_document_id(document_id: str) -> None:
    """
    Remove all vectors whose payload.document_id matches the given UUID.
    Useful for re-processing or deleting a document.
    """
    settings = get_settings()
    client = get_qdrant_client()

    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )
    logger.info("Deleted vectors for document_id=%s", document_id)


async def get_existing_point_ids(point_ids: list[str]) -> set[str]:
    """
    Given a list of Qdrant point IDs, returns a set of the ones that already exist
    in the collection. Useful for idempotent resumes to avoid re-embedding.
    """
    if not point_ids:
        return set()

    settings = get_settings()
    client = get_qdrant_client()

    # retrieve only the IDs without payload/vectors to be fast
    response = await client.retrieve(
        collection_name=settings.QDRANT_COLLECTION,
        ids=point_ids,
        with_payload=False,
        with_vectors=False
    )
    
    return {str(point.id) for point in response}







async def get_document_chunks(document_id: str, user_id: str) -> list[dict]:
    """Read indexed text only when both document and owner match in Qdrant."""
    settings = get_settings()
    client = get_qdrant_client()
    filters = qmodels.Filter(must=[
        qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id)),
        qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id)),
    ])
    offset = None
    chunks: list[dict] = []
    while True:
        points, next_offset = await client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=filters,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        chunks.extend(point.payload or {} for point in points)
        if next_offset is None:
            break
        offset = next_offset
    return sorted(chunks, key=lambda chunk: int(chunk.get("chunk_index", 0)))

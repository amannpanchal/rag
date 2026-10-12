"""Service package exports, loaded lazily to keep auth imports lightweight."""

from __future__ import annotations
from importlib import import_module
from typing import Any

_EXPORTS = {
    "get_health": ("app.services.health_service", "get_health"),
    "extract_pdf": ("app.services.pdf_service", "extract_pdf"),
    "embed_batch_with_retry": ("app.services.embedding_service", "embed_batch_with_retry"),
    "ensure_collection": ("app.services.vector_service", "ensure_collection"),
    "upsert_vectors": ("app.services.vector_service", "upsert_vectors"),
    "process_uploads": ("app.services.document_service", "process_uploads"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    return getattr(import_module(module_name), attribute)

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from app.config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = list(self._model.embed(texts))
        return [vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors]


_embedder: Embedder | None = None
_client: Any = None
_collection: Any = None
COLLECTION_NAME = "arx_chunks"


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        settings = get_settings()
        _embedder = FastEmbedEmbedder(settings.EMBEDDING_MODEL)
    return _embedder


def get_collection() -> Any:
    global _client, _collection
    if _collection is not None:
        return _collection
    import chromadb

    settings = get_settings()
    _client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def reset_vectorstore_for_tests() -> None:
    global _client, _collection
    _client = None
    _collection = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder = get_embedder()
    return embedder.embed(texts)


async def aembed_texts(texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(embed_texts, texts)


def upsert_chunks(
    *,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    collection = get_collection()
    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


async def aupsert_chunks(
    *,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    await asyncio.to_thread(
        upsert_chunks,
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query_chunks(*, embedding: list[float], n_results: int = 20, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    collection = get_collection()
    kwargs: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": max(n_results, 1),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    result = collection.query(**kwargs)
    items: list[dict[str, Any]] = []
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    for index, chunk_id in enumerate(ids):
        meta = metas[index] if index < len(metas) else {}
        distance = distances[index] if index < len(distances) else None
        score = None if distance is None else 1.0 - float(distance)
        items.append(
            {
                "id": chunk_id,
                "text": docs[index] if index < len(docs) else "",
                "document_id": str(meta.get("document_id", "")),
                "user_id": str(meta.get("user_id", "")),
                "filename": str(meta.get("filename", "")),
                "chunk_index": int(meta.get("chunk_index", 0) or 0),
                "heading": meta.get("heading"),
                "tags": _parse_tags(meta.get("tags")),
                "excluded": _truthy(meta.get("excluded")),
                "score": score,
            }
        )
    return items


async def aquery_chunks(
    *,
    embedding: list[float],
    n_results: int = 20,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(query_chunks, embedding=embedding, n_results=n_results, where=where)


def get_all_chunks(*, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    collection = get_collection()
    kwargs: dict[str, Any] = {"include": ["documents", "metadatas"]}
    if where:
        kwargs["where"] = where
    result = collection.get(**kwargs)
    items: list[dict[str, Any]] = []
    ids = result.get("ids") or []
    docs = result.get("documents") or []
    metas = result.get("metadatas") or []
    for index, chunk_id in enumerate(ids):
        meta = metas[index] if index < len(metas) else {}
        items.append(
            {
                "id": chunk_id,
                "text": docs[index] if index < len(docs) else "",
                "document_id": str(meta.get("document_id", "")),
                "user_id": str(meta.get("user_id", "")),
                "filename": str(meta.get("filename", "")),
                "chunk_index": int(meta.get("chunk_index", 0) or 0),
                "heading": meta.get("heading"),
                "tags": _parse_tags(meta.get("tags")),
                "excluded": _truthy(meta.get("excluded")),
            }
        )
    return items


async def aget_all_chunks(*, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return await asyncio.to_thread(get_all_chunks, where=where)


def delete_by_document_id(document_id: str) -> None:
    collection = get_collection()
    collection.delete(where={"document_id": document_id})


async def adelete_by_document_id(document_id: str) -> None:
    await asyncio.to_thread(delete_by_document_id, document_id)


def update_excluded_flag(document_id: str, excluded: bool) -> None:
    collection = get_collection()
    existing = collection.get(where={"document_id": document_id}, include=["metadatas", "documents", "embeddings"])
    ids = existing.get("ids") or []
    if not ids:
        return
    metas = existing.get("metadatas") or []
    new_metas = []
    for meta in metas:
        updated = dict(meta or {})
        updated["excluded"] = excluded
        new_metas.append(updated)
    collection.update(ids=ids, metadatas=new_metas)


async def aupdate_excluded_flag(document_id: str, excluded: bool) -> None:
    await asyncio.to_thread(update_excluded_flag, document_id, excluded)


def _parse_tags(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        if not raw:
            return []
        return [part for part in raw.split(",") if part]
    return [str(raw)]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)

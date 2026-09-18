from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.exclusions import filter_excluded
from app.core.intents import match_intent
from app.services import vectorstore
from app.services.rerank import cosine_similarity, rerank_entity_diverse

ANCHOR_THRESHOLD = 0.90

LayerName = Literal["intent", "anchor", "vector", "none"]


@dataclass
class RetrievalResult:
    layer: LayerName
    chunks: list[dict[str, Any]]


_anchors: list[dict[str, Any]] = []


def clear_anchors() -> None:
    _anchors.clear()


async def rebuild_anchors() -> None:
    """Rebuild in-memory semantic anchors from the current corpus."""
    chunks = await vectorstore.aget_all_chunks()
    visible = filter_excluded(chunks)
    by_doc: dict[str, list[dict[str, Any]]] = {}
    for chunk in visible:
        by_doc.setdefault(chunk["document_id"], []).append(chunk)
    new_anchors: list[dict[str, Any]] = []
    questions: list[str] = []
    payloads: list[list[dict[str, Any]]] = []
    for doc_id, doc_chunks in by_doc.items():
        ordered = sorted(doc_chunks, key=lambda item: int(item.get("chunk_index") or 0))
        first = ordered[0]
        heading = first.get("heading") or first.get("filename") or doc_id
        question = f"What does {first.get('filename', 'this document')} say about {heading}?"
        questions.append(question)
        payloads.append(ordered[:8])
    if not questions:
        _anchors.clear()
        return
    embeddings = await vectorstore.aembed_texts(questions)
    for question, embedding, payload in zip(questions, embeddings, payloads, strict=True):
        new_anchors.append({"question": question, "embedding": embedding, "chunks": payload})
    _anchors.clear()
    _anchors.extend(new_anchors)


def _by_tags(chunks: list[dict[str, Any]], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    wanted = {tag.lower() for tag in tags}
    matched: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_tags = {str(tag).lower() for tag in (chunk.get("tags") or [])}
        if chunk_tags & wanted:
            matched.append(chunk)
    return matched


async def layer_intent(query: str, *, user_id: str | None = None) -> list[dict[str, Any]]:
    rule = match_intent(query)
    if rule is None:
        return []
    chunks = await vectorstore.aget_all_chunks()
    # Structural exclusion runs inside the layer, not as a prompt instruction.
    visible = filter_excluded(chunks)
    if user_id:
        visible = [chunk for chunk in visible if chunk.get("user_id") in {user_id, "", None}]
    tagged = _by_tags(visible, rule.tags)
    for chunk in tagged:
        chunk["score"] = 1.0
    return rerank_entity_diverse(tagged)


async def layer_anchor(query: str) -> list[dict[str, Any]]:
    if not _anchors:
        await rebuild_anchors()
    if not _anchors:
        return []
    query_vec = (await vectorstore.aembed_texts([query]))[0]
    best_score = -1.0
    best_chunks: list[dict[str, Any]] = []
    for anchor in _anchors:
        score = cosine_similarity(query_vec, anchor["embedding"])
        if score > best_score:
            best_score = score
            best_chunks = list(anchor["chunks"])
    if best_score < ANCHOR_THRESHOLD:
        return []
    visible = filter_excluded(best_chunks)
    for chunk in visible:
        chunk["score"] = best_score
    return rerank_entity_diverse(visible)


async def layer_vector(query: str, *, n_results: int = 20) -> list[dict[str, Any]]:
    query_vec = (await vectorstore.aembed_texts([query]))[0]
    raw = await vectorstore.aquery_chunks(embedding=query_vec, n_results=n_results)
    visible = filter_excluded(raw)
    if not visible and raw:
        # Corpus existed but everything nearest was excluded — expand.
        more = await vectorstore.aquery_chunks(embedding=query_vec, n_results=max(n_results * 2, 40))
        visible = filter_excluded(more)
    ranked = rerank_entity_diverse(visible)
    return ranked


async def retrieve(query: str, *, user_id: str | None = None) -> RetrievalResult:
    """Stage 3 — 3-layer hybrid RAG. First confident layer wins."""
    intent_chunks = await layer_intent(query, user_id=user_id)
    if intent_chunks:
        return RetrievalResult(layer="intent", chunks=intent_chunks)

    anchor_chunks = await layer_anchor(query)
    if anchor_chunks:
        return RetrievalResult(layer="anchor", chunks=anchor_chunks)

    vector_chunks = await layer_vector(query)
    if vector_chunks:
        return RetrievalResult(layer="vector", chunks=vector_chunks)
    return RetrievalResult(layer="none", chunks=[])

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def _entity_key(chunk: dict[str, Any]) -> str:
    heading = chunk.get("heading")
    if heading:
        return str(heading)
    filename = chunk.get("filename")
    if filename:
        return str(filename)
    return str(chunk.get("document_id") or "unknown")


def rerank_entity_diverse(
    chunks: list[dict[str, Any]],
    *,
    final_k: int = 6,
    per_entity_cap: int = 2,
) -> list[dict[str, Any]]:
    """
    Cap how many of the final results any single entity may contribute.
    Entity is heading, then filename, then document_id.
    """
    scored = sorted(
        chunks,
        key=lambda item: float(item.get("score") or 0.0),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = defaultdict(int)
    overflow: list[dict[str, Any]] = []
    for chunk in scored:
        entity = _entity_key(chunk)
        enriched = {**chunk, "entity": entity}
        if counts[entity] < per_entity_cap and len(selected) < final_k:
            selected.append(enriched)
            counts[entity] += 1
        else:
            overflow.append(enriched)
    for chunk in overflow:
        if len(selected) >= final_k:
            break
        selected.append(chunk)
    return selected[:final_k]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)

from __future__ import annotations

import math

import pytest

from app.config import get_settings
from app.services.vectorstore import set_embedder


class DeterministicEmbedder:
    """Tiny local embedder so RAG tests never download FastEmbed weights."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * 32
            data = text.encode("utf-8")
            for index, byte in enumerate(data):
                vec[index % 32] += byte / 255.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vectors.append([x / norm for x in vec])
        return vectors


@pytest.fixture
def dummy_embedder() -> DeterministicEmbedder:
    embedder = DeterministicEmbedder()
    set_embedder(embedder)
    return embedder


@pytest.fixture
def settings():
    return get_settings()

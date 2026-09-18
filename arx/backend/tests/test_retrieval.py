from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.core.exclusions import filter_excluded
from app.services import retrieval, vectorstore


class DeterministicEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * 32
            data = text.encode("utf-8")
            for index, byte in enumerate(data):
                vec[index % 32] += byte / 255.0
            # Shared bias so nearest-neighbor search returns both docs.
            vec[0] += 2.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vectors.append([x / norm for x in vec])
        return vectors


@pytest.fixture
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DeterministicEmbedder:
    from app.config import get_settings

    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    get_settings.cache_clear()
    vectorstore.reset_vectorstore_for_tests()
    embedder = DeterministicEmbedder()
    vectorstore.set_embedder(embedder)
    retrieval.clear_anchors()
    return embedder


async def _seed(isolated_store: DeterministicEmbedder) -> None:
    included_text = "Visible ARX policy document about hybrid retrieval and FastEmbed."
    excluded_text = "SECRET excluded policy that must never surface in any retrieval layer."
    intent_text = "Intent target chunk about ARX_INTENT_PING quota pricing security."
    embeddings = isolated_store.embed([included_text, excluded_text, intent_text])
    vectorstore.upsert_chunks(
        ids=["inc:0", "exc:0", "int:0"],
        embeddings=embeddings,
        documents=[included_text, excluded_text, intent_text],
        metadatas=[
            {
                "document_id": "doc-included",
                "user_id": "u1",
                "filename": "visible.md",
                "chunk_index": 0,
                "heading": "Visible policy",
                "tags": "rag,quota",
                "excluded": False,
            },
            {
                "document_id": "doc-excluded",
                "user_id": "u1",
                "filename": "secret.md",
                "chunk_index": 0,
                "heading": "Secret policy",
                "tags": "intent-target,rag,quota",
                "excluded": True,
            },
            {
                "document_id": "doc-intent",
                "user_id": "u1",
                "filename": "intent.md",
                "chunk_index": 0,
                "heading": "Intent target",
                "tags": "intent-target",
                "excluded": False,
            },
        ],
    )
    await retrieval.rebuild_anchors()


def _assert_no_excluded(chunks: list[dict]) -> None:
    ids = {chunk.get("document_id") for chunk in chunks}
    assert "doc-excluded" not in ids
    for chunk in chunks:
        assert not chunk.get("excluded")


@pytest.mark.asyncio
async def test_exclusion_filter_all_three_layers(isolated_store: DeterministicEmbedder) -> None:
    await _seed(isolated_store)

    intent_chunks = await retrieval.layer_intent("please run ARX_INTENT_PING now")
    _assert_no_excluded(intent_chunks)
    assert intent_chunks
    assert any(chunk["document_id"] == "doc-intent" for chunk in intent_chunks)

    # Anchor question is generated from the first chunk of each document.
    anchor_chunks = await retrieval.layer_anchor("What does secret.md say about Secret policy?")
    _assert_no_excluded(anchor_chunks)

    vector_chunks = await retrieval.layer_vector("SECRET excluded policy that must never surface")
    _assert_no_excluded(vector_chunks)
    assert vector_chunks, "Layer 3 must still return included nearest neighbors"

    combined = await retrieval.retrieve("SECRET excluded policy that must never surface")
    _assert_no_excluded(combined.chunks)


@pytest.mark.asyncio
async def test_exclusion_filter_fails_if_removed(isolated_store: DeterministicEmbedder) -> None:
    await _seed(isolated_store)
    raw = await vectorstore.aget_all_chunks()
    excluded = [chunk for chunk in raw if chunk.get("document_id") == "doc-excluded"]
    assert excluded, "fixture must include an excluded chunk so removing the filter would fail the test"
    filtered = filter_excluded(raw)
    assert all(chunk.get("document_id") != "doc-excluded" for chunk in filtered)
    # If filter_excluded is a no-op, excluded docs leak.
    leaked = [chunk for chunk in filtered if chunk.get("document_id") == "doc-excluded"]
    assert leaked == []

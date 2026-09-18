from __future__ import annotations

import io
import re
from typing import Any

from app.services import vectorstore


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def parse_document(*, filename: str, mime_type: str, data: bytes) -> str:
    name = filename.lower()
    if mime_type == "application/pdf" or name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return "\n\n".join(pages)
    if (
        mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or name.endswith(".docx")
    ):
        from docx import Document

        document = Document(io.BytesIO(data))
        return "\n\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)
    if mime_type in {"text/markdown", "text/x-markdown"} or name.endswith(".md"):
        from markdown_it import MarkdownIt

        md = MarkdownIt()
        parsed = md.parse(data.decode("utf-8", errors="replace"))
        texts: list[str] = []
        for token in parsed:
            if token.type == "inline" and token.content:
                texts.append(token.content)
        return "\n\n".join(texts) if texts else data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


_HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Za-z0-9 /&-]{3,80})$", re.M)


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    return [part.strip() for part in parts if part.strip()]


def chunk_text(text: str, *, max_tokens: int = 800, overlap_tokens: int = 100) -> list[dict[str, Any]]:
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    current_tokens = 0
    heading: str | None = None

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        body = "\n\n".join(current).strip()
        if body:
            chunks.append({"text": body, "heading": heading})
        current = []
        current_tokens = 0

    for paragraph in paragraphs:
        first_line = paragraph.split("\n", 1)[0].strip()
        if _HEADING_RE.match(first_line):
            heading = first_line.lstrip("#").strip()
        tokens = _estimate_tokens(paragraph)
        if current_tokens + tokens > max_tokens and current:
            overlap_parts: list[str] = []
            overlap_count = 0
            for part in reversed(current):
                part_tokens = _estimate_tokens(part)
                if overlap_count + part_tokens > overlap_tokens:
                    break
                overlap_parts.insert(0, part)
                overlap_count += part_tokens
            flush()
            current = overlap_parts
            current_tokens = overlap_count
        current.append(paragraph)
        current_tokens += tokens
    flush()
    return chunks


async def embed_and_upsert(
    *,
    document_id: str,
    user_id: str,
    filename: str,
    chunks: list[dict[str, Any]],
    tags: list[str],
    excluded: bool,
) -> int:
    if not chunks:
        return 0
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        ids.append(f"{document_id}:{index}")
        documents.append(chunk["text"])
        metadatas.append(
            {
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename,
                "chunk_index": index,
                "heading": chunk.get("heading") or "",
                "tags": ",".join(tags),
                "excluded": excluded,
            }
        )
    embeddings: list[list[float]] = []
    batch_size = 64
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        embeddings.extend(await vectorstore.aembed_texts(batch))
    await vectorstore.aupsert_chunks(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    return len(chunks)


async def ingest_bytes(
    *,
    document_id: str,
    user_id: str,
    filename: str,
    mime_type: str,
    data: bytes,
    tags: list[str],
    excluded: bool = False,
) -> int:
    text = parse_document(filename=filename, mime_type=mime_type, data=data)
    chunks = chunk_text(text)
    return await embed_and_upsert(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        chunks=chunks,
        tags=tags,
        excluded=excluded,
    )

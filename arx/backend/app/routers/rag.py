from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from app.db import get_db
from app.deps import get_current_user
from app.errors import NotFoundError
from app.models.document import DocumentRecord, DocumentUpdate, RagSearchRequest, RagSearchResponse
from app.models.user import UserInDB
from app.services import ingest as ingest_service
from app.services import retrieval as retrieval_service
from app.services import vectorstore

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise NotFoundError("Document not found") from exc


def _record(doc: dict) -> DocumentRecord:
    return DocumentRecord(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        filename=doc["filename"],
        mime_type=doc.get("mime_type") or "application/octet-stream",
        size_bytes=int(doc.get("size_bytes") or 0),
        chunk_count=int(doc.get("chunk_count") or 0),
        status=doc.get("status") or "pending",
        excluded=bool(doc.get("excluded", False)),
        tags=doc.get("tags") or [],
        created_at=doc["created_at"],
        error=doc.get("error"),
    )


async def _process_document(document_id: str, user_id: str, filename: str, mime_type: str, data: bytes, tags: list[str]) -> None:
    db = get_db()
    oid = ObjectId(document_id)
    await db.documents.update_one({"_id": oid}, {"$set": {"status": "processing"}})
    try:
        chunk_count = await ingest_service.ingest_bytes(
            document_id=document_id,
            user_id=user_id,
            filename=filename,
            mime_type=mime_type,
            data=data,
            tags=tags,
            excluded=False,
        )
        await db.documents.update_one(
            {"_id": oid},
            {"$set": {"status": "ready", "chunk_count": chunk_count, "error": None}},
        )
        await retrieval_service.rebuild_anchors()
    except Exception as exc:
        await db.documents.update_one(
            {"_id": oid},
            {"$set": {"status": "failed", "error": str(exc)}},
        )


@router.post("/documents", response_model=DocumentRecord)
async def upload_document(
    background_tasks: BackgroundTasks,
    user: UserInDB = Depends(get_current_user),
    file: UploadFile = File(...),
    tags: str = Form(""),
) -> DocumentRecord:
    data = await file.read()
    tag_list = [item.strip() for item in tags.split(",") if item.strip()]
    now = datetime.now(timezone.utc)
    db = get_db()
    doc = {
        "user_id": user.id,
        "filename": file.filename or "upload",
        "mime_type": file.content_type or "application/octet-stream",
        "size_bytes": len(data),
        "chunk_count": 0,
        "status": "pending",
        "excluded": False,
        "tags": tag_list,
        "created_at": now,
        "error": None,
    }
    result = await db.documents.insert_one(doc)
    doc["_id"] = result.inserted_id
    background_tasks.add_task(
        _process_document,
        str(result.inserted_id),
        user.id,
        doc["filename"],
        doc["mime_type"],
        data,
        tag_list,
    )
    return _record(doc)


@router.get("/documents", response_model=list[DocumentRecord])
async def list_documents(user: UserInDB = Depends(get_current_user)) -> list[DocumentRecord]:
    db = get_db()
    query: dict = {} if user.role == "admin" else {"user_id": user.id}
    docs = await db.documents.find(query).sort("created_at", -1).to_list(length=500)
    return [_record(doc) for doc in docs]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    user: UserInDB = Depends(get_current_user),
) -> dict[str, bool]:
    db = get_db()
    query: dict = {"_id": _oid(document_id)}
    if user.role != "admin":
        query["user_id"] = user.id
    result = await db.documents.delete_one(query)
    if result.deleted_count == 0:
        raise NotFoundError("Document not found")
    await vectorstore.adelete_by_document_id(document_id)
    await retrieval_service.rebuild_anchors()
    return {"ok": True}


@router.patch("/documents/{document_id}", response_model=DocumentRecord)
async def patch_document(
    document_id: str,
    payload: DocumentUpdate,
    user: UserInDB = Depends(get_current_user),
) -> DocumentRecord:
    db = get_db()
    query: dict = {"_id": _oid(document_id)}
    if user.role != "admin":
        query["user_id"] = user.id
    updates = {key: value for key, value in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        doc = await db.documents.find_one(query)
        if doc is None:
            raise NotFoundError("Document not found")
        return _record(doc)
    result = await db.documents.update_one(query, {"$set": updates})
    if result.matched_count == 0:
        raise NotFoundError("Document not found")
    if "excluded" in updates:
        await vectorstore.aupdate_excluded_flag(document_id, bool(updates["excluded"]))
        await retrieval_service.rebuild_anchors()
    doc = await db.documents.find_one({"_id": _oid(document_id)})
    assert doc is not None
    return _record(doc)


@router.post("/search", response_model=RagSearchResponse)
async def search_rag(
    payload: RagSearchRequest,
    user: UserInDB = Depends(get_current_user),
) -> RagSearchResponse:
    result = await retrieval_service.retrieve(payload.query, user_id=user.id)
    chunks = []
    from app.models.document import RagChunk

    for chunk in result.chunks:
        chunks.append(
            RagChunk(
                document_id=str(chunk.get("document_id") or ""),
                filename=str(chunk.get("filename") or ""),
                chunk_index=int(chunk.get("chunk_index") or 0),
                heading=chunk.get("heading"),
                text=str(chunk.get("text") or ""),
                tags=list(chunk.get("tags") or []),
                excluded=bool(chunk.get("excluded", False)),
                score=chunk.get("score"),
                entity=chunk.get("entity"),
            )
        )
    return RagSearchResponse(layer=result.layer, chunks=chunks)

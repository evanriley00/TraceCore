from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import KnowledgeDocument
from app.db.session import session_scope
from app.schemas.decision import DocumentIngestRequest


class DocumentService:
    def ingest_document(self, db: Session, user_id: int, payload: DocumentIngestRequest) -> KnowledgeDocument:
        document = KnowledgeDocument(
            user_id=user_id,
            title=payload.title,
            content=payload.content,
            source=payload.source,
            tags=payload.tags,
            status="queued",
            meta_json={"content_length": len(payload.content)},
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document


def finalize_document_ingest(session_factory: sessionmaker, document_id: int) -> None:
    with session_scope(session_factory) as db:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            return
        document.status = "ready"
        document.meta_json = {
            **(document.meta_json or {}),
            "chunk_count_estimate": max(1, len(document.content) // 500),
            "indexed": True,
        }


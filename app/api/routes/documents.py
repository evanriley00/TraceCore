from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.decision import DocumentIngestRequest, DocumentRead
from app.services.document_service import DocumentService, finalize_document_ingest

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.post("/ingest", response_model=DocumentRead, status_code=status.HTTP_202_ACCEPTED)
def ingest_document(
    payload: DocumentIngestRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = DocumentService().ingest_document(db, current_user.id, payload)
    background_tasks.add_task(finalize_document_ingest, request.app.state.session_factory, document.id)
    return document


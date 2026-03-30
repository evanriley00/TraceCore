from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_rate_limiter, get_settings
from app.db.models import User
from app.schemas.decision import DecisionQuery, DecisionResponse, RunSummary
from app.services.cache import DecisionCache, RateLimiter
from app.services.query_service import DecisionService, finalize_learning_signal

router = APIRouter(prefix="/v1", tags=["queries"])


@router.post("/query", response_model=DecisionResponse)
def query(
    payload: DecisionQuery,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    cache: DecisionCache = request.app.state.cache
    service = DecisionService(settings=settings, cache=cache, rate_limiter=rate_limiter)
    response = service.process_query(db, current_user, payload)
    background_tasks.add_task(finalize_learning_signal, request.app.state.session_factory, response.request_id)
    return response


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    cache: DecisionCache = request.app.state.cache
    return DecisionService(settings=settings, cache=cache, rate_limiter=rate_limiter).list_runs(
        db,
        current_user.id,
    )


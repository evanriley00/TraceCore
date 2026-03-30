from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_rate_limiter, get_settings
from app.db.models import User
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.services.cache import DecisionCache, RateLimiter
from app.services.query_service import DecisionService

router = APIRouter(prefix="/v1", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(
    payload: FeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings=Depends(get_settings),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    cache: DecisionCache = request.app.state.cache
    return DecisionService(settings=settings, cache=cache, rate_limiter=rate_limiter).add_feedback(
        db,
        current_user,
        payload,
    )


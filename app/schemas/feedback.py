from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    request_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    user_id: int
    rating: int
    comment: str | None = None
    created_at: datetime


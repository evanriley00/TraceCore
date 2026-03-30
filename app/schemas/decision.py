from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    source: str
    snippet: str
    score: float
    document_id: int | None = None


class DecisionQuery(BaseModel):
    question: str = Field(min_length=3)
    session_key: str | None = None
    use_cache: bool = True


class DecisionResponse(BaseModel):
    request_id: int
    session_key: str
    query_type: str
    answer: str
    confidence: float
    cached: bool
    evaluation: dict
    evidence: list[EvidenceItem]
    run_id: int


class RunSummary(BaseModel):
    request_id: int
    question: str
    query_type: str | None = None
    status: str
    cache_hit: bool
    confidence: float | None = None
    overall_score: float | None = None
    created_at: datetime


class DocumentIngestRequest(BaseModel):
    title: str = Field(min_length=3)
    content: str = Field(min_length=20)
    source: str | None = None
    tags: list[str] = Field(default_factory=list)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source: str | None = None
    status: str
    tags: list[str]
    created_at: datetime


from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    api_key_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    requests: Mapped[list["QueryRequest"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")
    requests: Mapped[list["QueryRequest"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class QueryRequest(Base):
    __tablename__ = "query_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversation_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text)
    query_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    cache_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="requests")
    session: Mapped["ConversationSession | None"] = relationship(back_populates="requests")
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    output: Mapped["DecisionOutput | None"] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        uselist=False,
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("query_requests.id", ondelete="CASCADE"), index=True)
    workflow_name: Mapped[str] = mapped_column(String(100), default="tracecore-decision-graph")
    status: Mapped[str] = mapped_column(String(50), default="running")
    used_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)

    request: Mapped["QueryRequest"] = relationship(back_populates="agent_runs")
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(String(100))
    stage_name: Mapped[str] = mapped_column(String(100))
    tool_input: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_output: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent_run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")


class DecisionOutput(Base):
    __tablename__ = "decision_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("query_requests.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    answer: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    cached_response: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_trace: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped["QueryRequest"] = relationship(back_populates="output")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("query_requests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped["QueryRequest"] = relationship(back_populates="feedback_entries")
    user: Mapped["User"] = relationship(back_populates="feedback_entries")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    user: Mapped["User | None"] = relationship(back_populates="documents")


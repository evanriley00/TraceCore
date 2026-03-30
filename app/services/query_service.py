from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import AgentRun, ConversationSession, DecisionOutput, Feedback, QueryRequest, ToolCall, User
from app.ml.scorer import QueryScorer
from app.schemas.decision import DecisionQuery, DecisionResponse, RunSummary
from app.schemas.feedback import FeedbackCreate
from app.services.cache import DecisionCache, RateLimitExceeded, RateLimiter
from app.services.evaluation import EvaluationService
from app.services.tool_registry import ToolRegistry
from app.workflows.decision_graph import DecisionWorkflow


class DecisionService:
    def __init__(
        self,
        *,
        settings: Settings,
        cache: DecisionCache,
        rate_limiter: RateLimiter,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.rate_limiter = rate_limiter

    def process_query(self, db: Session, user: User, payload: DecisionQuery) -> DecisionResponse:
        try:
            self.rate_limiter.enforce(f"user:{user.id}:query")
        except RateLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(exc),
            ) from exc

        session_record = self._get_or_create_session(db, user.id, payload.session_key)
        cache_key = self._build_cache_key(user.id, session_record.session_key, payload.question)

        request_record = QueryRequest(
            user_id=user.id,
            session_id=session_record.id,
            question=payload.question,
            status="received",
            cache_key=cache_key,
            input_payload=payload.model_dump(),
            meta_json={"cache_backend": self.cache.backend_name},
        )
        db.add(request_record)
        db.commit()
        db.refresh(request_record)

        cached_payload = self.cache.get_json(cache_key) if payload.use_cache else None
        if cached_payload is not None:
            return self._complete_cached_request(
                db=db,
                request_record=request_record,
                session_record=session_record,
                cached_payload=cached_payload,
            )

        agent_run = AgentRun(
            request_id=request_record.id,
            workflow_name="tracecore-decision-graph",
            status="running",
            used_cache=False,
        )
        db.add(agent_run)
        db.commit()
        db.refresh(agent_run)

        scorer = QueryScorer()
        tool_registry = ToolRegistry(db, scorer)
        workflow = DecisionWorkflow(
            tool_registry=tool_registry,
            scorer=scorer,
            evaluation_service=EvaluationService(),
            settings=self.settings,
        )
        state = workflow.invoke(
            question=payload.question,
            user_id=user.id,
            session_id=session_record.id,
        )

        final_confidence = round(
            min(
                0.99,
                (0.65 * state["classification_confidence"])
                + (0.35 * state["evaluation"]["evidence_coverage"]),
            ),
            4,
        )

        output = DecisionOutput(
            request_id=request_record.id,
            answer=state["answer"],
            confidence=final_confidence,
            cached_response=False,
            evidence=state.get("evidence", []),
            evaluation=state["evaluation"],
            raw_trace={
                "history": state.get("history", []),
                "tool_calls": state.get("tool_calls", []),
                "probabilities": state.get("probabilities", {}),
            },
        )

        request_record.query_type = state["query_type"]
        request_record.status = "completed"
        request_record.cache_hit = False
        request_record.meta_json = {
            **(request_record.meta_json or {}),
            "model_name": state["model_name"],
        }
        session_record.last_seen_at = datetime.now(timezone.utc)

        agent_run.status = "completed"
        agent_run.model_name = state["model_name"]
        agent_run.completed_at = datetime.now(timezone.utc)
        agent_run.state_snapshot = {
            "query_type": state["query_type"],
            "evaluation": state["evaluation"],
            "tool_call_count": len(state.get("tool_calls", [])),
        }

        for tool_call in state.get("tool_calls", []):
            db.add(
                ToolCall(
                    agent_run_id=agent_run.id,
                    tool_name=tool_call["tool_name"],
                    stage_name=tool_call["stage_name"],
                    tool_input=tool_call["tool_input"],
                    tool_output=tool_call["tool_output"],
                    latency_ms=tool_call["latency_ms"],
                )
            )

        db.add(output)
        db.commit()

        response_payload = self._serialize_response(
            request_id=request_record.id,
            session_key=session_record.session_key,
            query_type=state["query_type"],
            answer=state["answer"],
            confidence=final_confidence,
            cached=False,
            evaluation=state["evaluation"],
            evidence=state.get("evidence", []),
            run_id=agent_run.id,
        )

        if payload.use_cache:
            self.cache.set_json(cache_key, response_payload, self.settings.cache_ttl_seconds)

        return DecisionResponse(**response_payload)

    def list_runs(self, db: Session, user_id: int) -> list[RunSummary]:
        rows = db.execute(
            select(QueryRequest, DecisionOutput)
            .outerjoin(DecisionOutput, DecisionOutput.request_id == QueryRequest.id)
            .where(QueryRequest.user_id == user_id)
            .order_by(desc(QueryRequest.created_at))
            .limit(25)
        ).all()

        return [
            RunSummary(
                request_id=query.id,
                question=query.question,
                query_type=query.query_type,
                status=query.status,
                cache_hit=query.cache_hit,
                confidence=output.confidence if output is not None else None,
                overall_score=(output.evaluation or {}).get("overall_score") if output is not None else None,
                created_at=query.created_at,
            )
            for query, output in rows
        ]

    def add_feedback(self, db: Session, user: User, payload: FeedbackCreate) -> Feedback:
        request_record = db.scalar(
            select(QueryRequest).where(QueryRequest.id == payload.request_id, QueryRequest.user_id == user.id)
        )
        if request_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        feedback = Feedback(
            request_id=request_record.id,
            user_id=user.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    def _get_or_create_session(self, db: Session, user_id: int, session_key: str | None) -> ConversationSession:
        if session_key:
            session_record = db.scalar(
                select(ConversationSession).where(
                    ConversationSession.user_id == user_id,
                    ConversationSession.session_key == session_key,
                )
            )
            if session_record is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            return session_record

        session_record = ConversationSession(
            user_id=user_id,
            session_key=uuid4().hex,
            title="TraceCore session",
        )
        db.add(session_record)
        db.commit()
        db.refresh(session_record)
        return session_record

    def _build_cache_key(self, user_id: int, session_key: str, question: str) -> str:
        raw = f"{user_id}:{session_key}:{question.strip().lower()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _serialize_response(
        self,
        *,
        request_id: int,
        session_key: str,
        query_type: str,
        answer: str,
        confidence: float,
        cached: bool,
        evaluation: dict,
        evidence: list[dict],
        run_id: int,
    ) -> dict:
        return {
            "request_id": request_id,
            "session_key": session_key,
            "query_type": query_type,
            "answer": answer,
            "confidence": confidence,
            "cached": cached,
            "evaluation": evaluation,
            "evidence": evidence,
            "run_id": run_id,
        }

    def _complete_cached_request(
        self,
        *,
        db: Session,
        request_record: QueryRequest,
        session_record: ConversationSession,
        cached_payload: dict,
    ) -> DecisionResponse:
        agent_run = AgentRun(
            request_id=request_record.id,
            workflow_name="tracecore-decision-graph",
            status="completed",
            used_cache=True,
            model_name="response-cache",
            completed_at=datetime.now(timezone.utc),
            state_snapshot={"cache_hit": True},
        )
        db.add(agent_run)
        db.commit()
        db.refresh(agent_run)

        evaluation = {
            **cached_payload["evaluation"],
            "cached_penalty_applied": True,
        }
        output = DecisionOutput(
            request_id=request_record.id,
            answer=cached_payload["answer"],
            confidence=cached_payload["confidence"],
            cached_response=True,
            evidence=cached_payload["evidence"],
            evaluation=evaluation,
            raw_trace={"cache_hit": True},
        )
        request_record.query_type = cached_payload["query_type"]
        request_record.status = "completed"
        request_record.cache_hit = True
        session_record.last_seen_at = datetime.now(timezone.utc)
        db.add(output)
        db.add(
            ToolCall(
                agent_run_id=agent_run.id,
                tool_name="response_cache",
                stage_name="lookup",
                tool_input={"cache_key": request_record.cache_key},
                tool_output={"hit": True},
                latency_ms=0.0,
            )
        )
        db.commit()

        return DecisionResponse(
            **self._serialize_response(
                request_id=request_record.id,
                session_key=session_record.session_key,
                query_type=cached_payload["query_type"],
                answer=cached_payload["answer"],
                confidence=cached_payload["confidence"],
                cached=True,
                evaluation=evaluation,
                evidence=cached_payload["evidence"],
                run_id=agent_run.id,
            )
        )


def finalize_learning_signal(session_factory: sessionmaker, request_id: int) -> None:
    with session_factory() as db:
        request_record = db.get(QueryRequest, request_id)
        output = db.scalar(select(DecisionOutput).where(DecisionOutput.request_id == request_id))
        if request_record is None or output is None:
            return
        request_record.meta_json = {
            **(request_record.meta_json or {}),
            "post_processed_at": datetime.now(timezone.utc).isoformat(),
            "needs_review": output.evaluation.get("overall_score", 0.0) < 0.55,
        }
        db.commit()


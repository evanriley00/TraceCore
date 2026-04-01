from __future__ import annotations

import time
import re

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.db.models import DecisionOutput, KnowledgeDocument, QueryRequest
from app.ml.scorer import QueryScorer

REFERENTIAL_QUERY_TOKENS = {
    "this",
    "that",
    "it",
    "content",
    "document",
    "documents",
    "doc",
    "file",
    "text",
    "material",
    "uploaded",
    "upload",
}


class ToolRegistry:
    def __init__(self, db: Session, scorer: QueryScorer) -> None:
        self.db = db
        self.scorer = scorer

    def load_session_history(self, user_id: int, session_id: int | None) -> tuple[list[dict], dict]:
        started_at = time.perf_counter()
        history: list[dict] = []

        if session_id is not None:
            rows = self.db.execute(
                select(QueryRequest, DecisionOutput)
                .join(DecisionOutput, DecisionOutput.request_id == QueryRequest.id)
                .where(QueryRequest.user_id == user_id, QueryRequest.session_id == session_id)
                .order_by(desc(QueryRequest.created_at))
                .limit(3)
            ).all()

            history = [
                {
                    "question": query.question,
                    "answer": output.answer,
                    "created_at": query.created_at.isoformat(),
                }
                for query, output in rows
            ]

        latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
        return history, {
            "tool_name": "session_history_lookup",
            "stage_name": "retrieve",
            "tool_input": {"user_id": user_id, "session_id": session_id},
            "tool_output": {"items": len(history)},
            "latency_ms": latency_ms,
        }

    def search_documents(self, user_id: int, question: str, top_k: int = 3) -> tuple[list[dict], dict]:
        started_at = time.perf_counter()
        rows = self.db.scalars(
            select(KnowledgeDocument)
            .where(
                or_(KnowledgeDocument.user_id == user_id, KnowledgeDocument.user_id.is_(None)),
                KnowledgeDocument.status.in_(("ready", "queued")),
            )
            .order_by(desc(KnowledgeDocument.updated_at))
            .limit(25)
        ).all()

        prepared_docs = [
            {
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "tags": row.tags or [],
                "source": row.source or row.title,
            }
            for row in rows
        ]

        ranked = self.scorer.rerank_documents(question, prepared_docs)[:top_k]
        evidence = [self._serialize_evidence(item) for item in ranked if item["score"] > 0]
        fallback_used = False

        if not evidence:
            fallback_document = self._referential_fallback(rows, user_id, question)
            if fallback_document is not None:
                evidence = [self._serialize_document_row(fallback_document, score=0.18)]
                fallback_used = True

        latency_ms = round((time.perf_counter() - started_at) * 1000, 3)

        return evidence, {
            "tool_name": "document_search",
            "stage_name": "retrieve",
            "tool_input": {"user_id": user_id, "question": question},
            "tool_output": {"matches": len(evidence), "fallback_used": fallback_used},
            "latency_ms": latency_ms,
        }

    def _serialize_evidence(self, document: dict) -> dict:
        return {
            "document_id": document["id"],
            "source": document["source"],
            "snippet": document["content"][:220],
            "score": document["score"],
        }

    def _serialize_document_row(self, document: KnowledgeDocument, *, score: float) -> dict:
        return {
            "document_id": document.id,
            "source": document.source or document.title,
            "snippet": document.content[:220],
            "score": score,
        }

    def _referential_fallback(
        self,
        rows: list[KnowledgeDocument],
        user_id: int,
        question: str,
    ) -> KnowledgeDocument | None:
        if not self._looks_referential(question):
            return None

        for row in rows:
            if row.user_id == user_id:
                return row

        return None

    def _looks_referential(self, question: str) -> bool:
        tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
        return bool(tokens & REFERENTIAL_QUERY_TOKENS)

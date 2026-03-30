from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import Settings
from app.ml.scorer import QueryScorer
from app.services.evaluation import EvaluationService
from app.services.llm import _format_evidence, _format_history, build_reasoning_chain
from app.services.tool_registry import ToolRegistry


class DecisionState(TypedDict, total=False):
    question: str
    user_id: int
    session_id: int | None
    query_type: str
    classification_confidence: float
    probabilities: dict[str, float]
    history: list[dict]
    evidence: list[dict]
    tool_calls: list[dict]
    answer: str
    evaluation: dict
    model_name: str


class DecisionWorkflow:
    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        scorer: QueryScorer,
        evaluation_service: EvaluationService,
        settings: Settings,
    ) -> None:
        self.tool_registry = tool_registry
        self.scorer = scorer
        self.evaluation_service = evaluation_service
        self.reasoning_chain, self.model_name = build_reasoning_chain(settings)
        graph = StateGraph(DecisionState)
        graph.add_node("classify", self.classify_node)
        graph.add_node("retrieve", self.retrieve_node)
        graph.add_node("reason", self.reason_node)
        graph.add_node("evaluate", self.evaluate_node)
        graph.set_entry_point("classify")
        graph.add_edge("classify", "retrieve")
        graph.add_edge("retrieve", "reason")
        graph.add_edge("reason", "evaluate")
        graph.add_edge("evaluate", END)
        self.graph = graph.compile()

    def invoke(self, *, question: str, user_id: int, session_id: int | None) -> DecisionState:
        return self.graph.invoke(
            {
                "question": question,
                "user_id": user_id,
                "session_id": session_id,
                "tool_calls": [],
            }
        )

    def classify_node(self, state: DecisionState) -> DecisionState:
        prediction = self.scorer.predict_query_type(state["question"])
        return {
            "query_type": prediction.label,
            "classification_confidence": prediction.confidence,
            "probabilities": prediction.probabilities,
        }

    def retrieve_node(self, state: DecisionState) -> DecisionState:
        history, history_log = self.tool_registry.load_session_history(
            state["user_id"],
            state.get("session_id"),
        )
        evidence, search_log = self.tool_registry.search_documents(
            state["user_id"],
            state["question"],
        )
        return {
            "history": history,
            "evidence": evidence,
            "tool_calls": [*state.get("tool_calls", []), history_log, search_log],
        }

    def reason_node(self, state: DecisionState) -> DecisionState:
        answer = self.reasoning_chain.invoke(
            {
                "question": state["question"],
                "query_type": state["query_type"],
                "history": _format_history(state.get("history", [])),
                "evidence": _format_evidence(state.get("evidence", [])),
            }
        )
        return {
            "answer": answer,
            "model_name": self.model_name,
        }

    def evaluate_node(self, state: DecisionState) -> DecisionState:
        evaluation = self.evaluation_service.evaluate(
            question=state["question"],
            answer=state["answer"],
            evidence=state.get("evidence", []),
            query_type=state["query_type"],
            confidence=state["classification_confidence"],
            used_cache=False,
        )
        return {"evaluation": evaluation}


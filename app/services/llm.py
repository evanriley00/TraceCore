from __future__ import annotations

from collections.abc import Iterable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings


def _flatten_messages(prompt_value) -> str:
    if hasattr(prompt_value, "to_messages"):
        messages = prompt_value.to_messages()
        return "\n".join(f"{message.type.upper()}: {message.content}" for message in messages)
    return str(prompt_value)


def _mock_reasoner(prompt_value) -> str:
    prompt_text = _flatten_messages(prompt_value)
    evidence_lines = [line.strip("- ").strip() for line in prompt_text.splitlines() if line.strip().startswith("- ")]
    evidence_summary = "; ".join(evidence_lines[:2]) if evidence_lines else "no stored evidence"

    question = "the user query"
    for line in prompt_text.splitlines():
        if line.startswith("Question: "):
            question = line.removeprefix("Question: ").strip()
            break

    return (
        f"Recommendation: Focus on the most defensible answer to '{question}'.\n"
        f"Reasoning: The engine classified the request, checked session history, and used retrieved evidence to ground the decision.\n"
        f"Evidence: {evidence_summary}.\n"
        f"Next step: Collect user feedback so future runs can calibrate confidence and improve retrieval."
    )


def _format_history(history: Iterable[dict]) -> str:
    items = list(history)
    if not items:
        return "No prior session history."
    return "\n".join(
        f"- Q: {item['question']} | A: {item['answer'][:120]}"
        for item in items
    )


def _format_evidence(evidence: Iterable[dict]) -> str:
    items = list(evidence)
    if not items:
        return "No evidence retrieved."
    return "\n".join(
        f"- {item['source']}: {item['snippet']} (score={item['score']})"
        for item in items
    )


def build_reasoning_chain(settings: Settings):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are TraceCore, an AI decision engine. Produce concise, evidence-aware recommendations and explain the reasoning.",
            ),
            (
                "human",
                "Question: {question}\n"
                "Query type: {query_type}\n"
                "Session history:\n{history}\n"
                "Retrieved evidence:\n{evidence}\n"
                "Return a recommendation, reasoning, evidence summary, and next step.",
            ),
        ]
    )

    if not settings.mock_llm_enabled and settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=0.2,
            )
            return prompt | llm | StrOutputParser(), settings.openai_model
        except Exception:
            pass

    return prompt | RunnableLambda(_mock_reasoner) | StrOutputParser(), "tracecore-mock-reasoner"


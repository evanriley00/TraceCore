from __future__ import annotations


class EvaluationService:
    def evaluate(
        self,
        *,
        question: str,
        answer: str,
        evidence: list[dict],
        query_type: str,
        confidence: float,
        used_cache: bool,
    ) -> dict:
        question_terms = {token for token in question.lower().split() if len(token) > 3}
        answer_terms = {token for token in answer.lower().split() if len(token) > 3}
        overlap = len(question_terms & answer_terms) / max(1, len(question_terms))
        evidence_coverage = min(1.0, len(evidence) / 3)
        answer_depth = min(1.0, len(answer.split()) / 85)
        cache_penalty = 0.05 if used_cache else 0.0

        overall_score = max(
            0.0,
            round(
                (0.35 * overlap) + (0.35 * evidence_coverage) + (0.30 * confidence) - cache_penalty,
                4,
            ),
        )

        improvement_hint = "Response looks healthy."
        if evidence_coverage < 0.34:
            improvement_hint = "Ingest more domain documents so the engine can cite stronger evidence."
        elif overlap < 0.4:
            improvement_hint = "Prompt and model alignment can be improved to anchor the answer more tightly to the question."

        return {
            "query_type": query_type,
            "question_answer_overlap": round(overlap, 4),
            "evidence_coverage": round(evidence_coverage, 4),
            "answer_depth": round(answer_depth, 4),
            "overall_score": overall_score,
            "cached_penalty_applied": used_cache,
            "improvement_hint": improvement_hint,
        }


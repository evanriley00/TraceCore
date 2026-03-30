from __future__ import annotations

import re
from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F


VOCAB = [
    "start",
    "sit",
    "player",
    "lineup",
    "sports",
    "summarize",
    "summary",
    "topic",
    "evidence",
    "source",
    "analyze",
    "analysis",
    "data",
    "recommend",
    "recommendation",
    "forecast",
    "risk",
    "compare",
]

LABELS = [
    "sports_start_decision",
    "evidence_summary",
    "data_recommendation",
    "general_decision",
]


@dataclass
class QueryPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


class QueryIntentNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(len(VOCAB), len(LABELS), bias=True)
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        with torch.no_grad():
            self.linear.weight.zero_()
            self.linear.bias.fill_(-0.4)

            sports_tokens = ["start", "sit", "player", "lineup", "sports"]
            summary_tokens = ["summarize", "summary", "topic", "evidence", "source"]
            data_tokens = ["analyze", "analysis", "data", "recommend", "recommendation", "forecast", "risk", "compare"]

            for token in sports_tokens:
                self.linear.weight[0, VOCAB.index(token)] = 1.6
            for token in summary_tokens:
                self.linear.weight[1, VOCAB.index(token)] = 1.5
            for token in data_tokens:
                self.linear.weight[2, VOCAB.index(token)] = 1.4
            self.linear.weight[3, :] = 0.35
            self.linear.bias[3] = 0.2

    def forward(self, inputs: Tensor) -> Tensor:
        return self.linear(inputs)


class QueryScorer:
    def __init__(self) -> None:
        self.model = QueryIntentNet()
        self.model.eval()

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def encode_text(self, text: str) -> Tensor:
        tokens = self._tokenize(text)
        counts = [float(tokens.count(token)) for token in VOCAB]
        return torch.tensor(counts, dtype=torch.float32)

    def predict_query_type(self, question: str) -> QueryPrediction:
        vector = self.encode_text(question)
        with torch.no_grad():
            logits = self.model(vector)
            probabilities = torch.softmax(logits, dim=0)
        best_index = int(torch.argmax(probabilities).item())
        probability_map = {
            label: round(float(probabilities[index].item()), 4)
            for index, label in enumerate(LABELS)
        }
        return QueryPrediction(
            label=LABELS[best_index],
            confidence=round(float(probabilities[best_index].item()), 4),
            probabilities=probability_map,
        )

    def rerank_documents(self, question: str, documents: list[dict]) -> list[dict]:
        if not documents:
            return []

        question_vec = self.encode_text(question)
        question_norm = question_vec.norm().item()
        question_tokens = set(self._tokenize(question))
        ranked: list[dict] = []

        for document in documents:
            doc_text = " ".join(
                [
                    document.get("title", ""),
                    document.get("content", ""),
                    " ".join(document.get("tags", [])),
                ]
            )
            doc_vec = self.encode_text(doc_text)
            doc_norm = doc_vec.norm().item()
            doc_tokens = set(self._tokenize(doc_text))
            cosine = 0.0
            if question_norm > 0 and doc_norm > 0:
                cosine = float(
                    F.cosine_similarity(question_vec.unsqueeze(0), doc_vec.unsqueeze(0)).item()
                )

            vocab_overlap = float(torch.minimum(question_vec, doc_vec).sum().item())
            lexical_overlap = 0.0
            if question_tokens:
                lexical_overlap = len(question_tokens & doc_tokens) / len(question_tokens)

            score = round(
                (0.55 * cosine)
                + (0.20 * min(1.0, vocab_overlap / 3.0))
                + (0.25 * lexical_overlap),
                4,
            )
            ranked.append({**document, "score": score})

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

from app.ml.scorer import QueryScorer


def test_query_scorer_classifies_summary_questions():
    scorer = QueryScorer()
    prediction = scorer.predict_query_type("Summarize this topic and provide evidence")
    assert prediction.label == "evidence_summary"
    assert prediction.confidence > 0.35


def test_query_scorer_reranks_relevant_documents_first():
    scorer = QueryScorer()
    ranked = scorer.rerank_documents(
        "Analyze this data and recommend an action",
        [
            {"id": 1, "title": "Travel Guide", "content": "A guide about beaches and flights.", "tags": ["travel"]},
            {"id": 2, "title": "Data Review", "content": "Data analysis techniques for recommendation systems.", "tags": ["data", "analysis"]},
        ],
    )
    assert ranked[0]["id"] == 2
    assert ranked[0]["score"] >= ranked[1]["score"]


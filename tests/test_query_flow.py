def _register_headers(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "analyst@example.com",
            "password": "super-secret-password",
            "full_name": "Data Analyst",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_ingest_query_cache_and_feedback_flow(client):
    headers = _register_headers(client)

    ingest_response = client.post(
        "/v1/documents/ingest",
        headers=headers,
        json={
            "title": "Solar Energy Brief",
            "content": "Solar energy reduces long-term electricity costs, improves grid resilience, and lowers carbon emissions when deployed at scale.",
            "source": "internal_research",
            "tags": ["energy", "solar", "costs"],
        },
    )
    assert ingest_response.status_code == 202
    assert ingest_response.json()["status"] == "queued"

    query_payload = {
        "question": "Summarize solar energy and give evidence for the recommendation",
        "use_cache": True,
    }
    first_query = client.post("/v1/query", headers=headers, json=query_payload)
    assert first_query.status_code == 200
    first_result = first_query.json()
    assert first_result["cached"] is False
    assert first_result["query_type"] == "evidence_summary"
    assert len(first_result["evidence"]) >= 1
    assert first_result["evaluation"]["overall_score"] > 0

    second_query = client.post(
        "/v1/query",
        headers=headers,
        json={**query_payload, "session_key": first_result["session_key"]},
    )
    assert second_query.status_code == 200
    second_result = second_query.json()
    assert second_result["cached"] is True

    runs_response = client.get("/v1/runs", headers=headers)
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) >= 2

    feedback_response = client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "request_id": first_result["request_id"],
            "rating": 5,
            "comment": "Grounded and clear",
        },
    )
    assert feedback_response.status_code == 201
    assert feedback_response.json()["rating"] == 5


def test_recent_uploaded_document_is_used_for_referential_summary_queries(client):
    headers = _register_headers(client)

    ingest_response = client.post(
        "/v1/documents/ingest",
        headers=headers,
        json={
            "title": "UDSS",
            "content": (
                "Universal Design for Student Success helps educators present material in multiple ways, "
                "offer flexible participation options, and remove learning barriers before students hit them."
            ),
            "source": "UDSS",
            "tags": ["education", "framework"],
        },
    )
    assert ingest_response.status_code == 202
    assert ingest_response.json()["status"] == "queued"

    query_response = client.post(
        "/v1/query",
        headers=headers,
        json={
            "question": "Summarize this content and explain it easily.",
            "use_cache": False,
        },
    )
    assert query_response.status_code == 200
    payload = query_response.json()

    assert payload["query_type"] == "evidence_summary"
    assert len(payload["evidence"]) >= 1
    assert payload["evidence"][0]["source"] == "UDSS"
    assert "Universal Design for Student Success" in payload["evidence"][0]["snippet"]

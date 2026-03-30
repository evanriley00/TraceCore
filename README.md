# TraceCore

TraceCore is a production-style AI decision engine. It is designed to feel like a real backend system instead of a chatbot demo:

- FastAPI API with JWT and API key authentication
- PostgreSQL-ready SQLAlchemy persistence
- LangGraph workflow orchestration with LangChain prompts
- Redis-backed caching and rate limiting with in-memory fallback
- PyTorch-based query classification and evidence reranking
- Background jobs for ingestion and post-run learning signals
- Evaluation, feedback capture, and run history endpoints

## Core Flow

1. A user registers or logs in.
2. The user submits a protected query to `/v1/query`.
3. TraceCore stores the request and runs a LangGraph workflow.
4. The workflow classifies the query, retrieves evidence, reasons over it, and scores the response.
5. The system logs runs, tool calls, outputs, feedback, and evaluation metadata.
6. Expensive responses can be served from cache on later calls.

## Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /v1/documents/ingest`
- `POST /v1/query`
- `GET /v1/runs`
- `POST /v1/feedback`
- `GET /health`

## Running Locally

### Quick Start Without Docker

1. Copy `.env.example` to `.env`.
2. Install the app with `pip install -e .[dev]`.
3. Run the API with `python -m uvicorn app.main:app --reload`.
4. Open `http://127.0.0.1:8000/ui` for the guided control panel.
5. Open `http://127.0.0.1:8000/docs` if you want the raw Swagger view too.

This path uses SQLite by default and falls back to in-memory caching if Redis is not running.

### Optional Production-Style Infra

1. Start Docker Desktop.
2. Run `docker compose up postgres redis -d`.
3. Change `DATABASE_URL` in `.env` to `postgresql+psycopg://tracecore:tracecore@localhost:5432/tracecore`.
4. Start the API with `python -m uvicorn app.main:app --reload`.

Run tests with `python -m pytest`.

## Notes

- By default the workflow uses a deterministic mock reasoner so tests stay stable.
- If `OPENAI_API_KEY` is set and `MOCK_LLM_ENABLED=false`, the reasoning stage will use `langchain-openai`.
- The default retrieval path uses stored documents and prior session history.

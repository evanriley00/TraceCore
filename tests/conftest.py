from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'tracecore_test.db'}",
        redis_url="redis://localhost:6399/0",
        jwt_secret="test-secret-for-tracecore-suite-1234567890",
        rate_limit_per_minute=100,
        mock_llm_enabled=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client

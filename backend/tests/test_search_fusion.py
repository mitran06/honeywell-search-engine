import sys
import pathlib
import uuid

# Ensure backend package importable when running pytest from backend/
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings

# Queries we expect to return matches in the uploaded AI-Driven document
TEST_QUERIES = [
    "document processing pipeline",
    "NVIDIA NeMo embeddings",
    "caching and load balancing",
    "how does the system scale",
    "streaming real-time responses",
]

# Sync DB for test introspection
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def _latest_completed_pdf():
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT id, uploaded_by, filename
                FROM pdf_metadata
                WHERE status = 'COMPLETED'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        ).fetchone()
        return row
    finally:
        db.close()


class DummyUser(User):
    def __init__(self, user_id: uuid.UUID, email: str = "tester@example.com"):
        self.id = user_id
        self.email = email
        self.name = "Tester"


def make_fake_current_user(user_id: uuid.UUID):
    def _fake_user():
        return DummyUser(user_id)
    return _fake_user


@pytest.fixture(autouse=True)
def override_deps():
    row = _latest_completed_pdf()
    if not row:
        pytest.skip("No completed PDF found in database for search test")

    pdf_id, uploaded_by, _filename = row
    app.dependency_overrides[get_current_user] = make_fake_current_user(uploaded_by)
    yield
    app.dependency_overrides.clear()


def test_search_fusion_end_to_end():
    row = _latest_completed_pdf()
    if not row:
        pytest.skip("No completed PDF found in database for search test")

    with TestClient(app) as client:
        for query in TEST_QUERIES:
            resp = client.post(
                "/api/search",
                json={
                    "query": query,
                    "limit": 5,
                },
            )
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            assert payload.get("success") is True
            data = payload.get("data") or {}
            results = data.get("results") or []
            assert len(results) > 0, f"Expected results for query: {query}"

            # Validate score breakdown presence
            for r in results:
                scores = r.get("scores") or {}
                for key in ("fusion", "semantic", "lexical", "triple"):
                    assert key in scores, f"Missing score '{key}' in result for query: {query}"
                assert 0.0 <= r.get("confidenceScore", 0) <= 100.0

            # Log first result for debug
            top = results[0]
            print(f"Query='{query}' -> top fusion={top['scores']['fusion']:.3f} text='{top['snippet'][:80]}...'")

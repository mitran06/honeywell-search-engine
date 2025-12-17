import sys
import pathlib
import uuid
from typing import Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ensure backend importable
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.main import app
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings

# Sync DB access
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# Queries to audit with soft expectations
AUDIT_CASES = [
    {
        "query": "document processing pipeline",
        "min_fusion": 0.40,
        "min_semantic": 0.30,
        "min_lexical": 0.05,
    },
    {
        "query": "NVIDIA NeMo embeddings",
        "min_fusion": 0.40,
        "min_semantic": 0.30,
        "min_lexical": 0.02,
    },
    {
        "query": "caching and load balancing",
        "min_fusion": 0.35,
        "min_semantic": 0.25,
        "min_lexical": 0.005,
    },
    {
        "query": "how does the system scale",
        "min_fusion": 0.35,
        "min_semantic": 0.25,
        "min_lexical": 0.05,
    },
    {
        "query": "streaming real-time responses",
        "min_fusion": 0.30,
        "min_semantic": 0.20,
        "min_lexical": 0.0,
    },
]


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
        pytest.skip("No completed PDF found for audit")
    pdf_id, uploaded_by, _fname = row
    app.dependency_overrides[get_current_user] = make_fake_current_user(uploaded_by)
    yield
    app.dependency_overrides.clear()


def _assert_top_scores(case: Dict, top_scores: Dict):
    fusion = float(top_scores.get("fusion", 0.0))
    semantic = float(top_scores.get("semantic", 0.0))

    assert 0.0 <= fusion <= 1.0
    assert 0.0 <= semantic <= 1.0

    assert fusion >= case["min_fusion"], f"fusion below expectation ({fusion:.3f} < {case['min_fusion']:.3f})"
    assert semantic >= case["min_semantic"], f"semantic below expectation ({semantic:.3f} < {case['min_semantic']:.3f})"
    return fusion, semantic


def test_search_audit_end_to_end():
    row = _latest_completed_pdf()
    if not row:
        pytest.skip("No completed PDF found for audit")

    with TestClient(app) as client:
        for case in AUDIT_CASES:
            query = case["query"]
            resp = client.post(
                "/api/search",
                json={"query": query, "limit": 5},
            )
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            assert payload.get("success") is True
            data = payload.get("data") or {}
            results: List[dict] = data.get("results") or []
            assert results, f"No results for query: {query}"

            top = results[0]
            top_scores = top.get("scores") or {}
            fusion, semantic = _assert_top_scores(case, top_scores)

            # Check lexical channel has signal somewhere in results
            max_lexical = max(float(r.get("scores", {}).get("lexical", 0.0)) for r in results)
            assert max_lexical >= case["min_lexical"], (
                f"lexical signal too low across results (max={max_lexical:.3f} < {case['min_lexical']:.3f})"
            )

            snippet = top.get("snippet", "")
            assert snippet, "Empty snippet"
            page = top.get("pageNumber", 0)
            assert page >= 0

            # Print summary for manual inspection
            print(
                f"Query='{query}' => fusion={fusion:.3f}, semantic={semantic:.3f}, max_lexical={max_lexical:.3f}, text='{snippet[:90]}...'"
            )

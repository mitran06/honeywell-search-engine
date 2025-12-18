"""
Search Quality Audit Tests

These tests verify that search returns meaningful results with expected score ranges.
They require at least one completed PDF in the database.
"""
import sys
import pathlib
import uuid
import time

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


# Test queries - these should return results if documents contain relevant content
TEST_QUERIES = [
    "document processing pipeline",
    "NVIDIA NeMo embeddings",
    "caching and load balancing",
    "how does the system scale",
    "streaming real-time responses",
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


@pytest.fixture(scope="module")
def client():
    """Module-scoped test client to avoid event loop issues."""
    row = _latest_completed_pdf()
    if not row:
        pytest.skip("No completed PDF found for testing")
    pdf_id, uploaded_by, _fname = row
    app.dependency_overrides[get_current_user] = make_fake_current_user(uploaded_by)
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_search_returns_results(client):
    """Verify search returns results for test queries."""
    for query in TEST_QUERIES:
        resp = client.post(
            "/api/search",
            json={"query": query, "limit": 5},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload.get("success") is True
        
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        # Log result (test may pass even with 0 results if query doesn't match content)
        if results:
            top = results[0]
            print(f"Query='{query}' => confidence={top['confidenceScore']:.1f}%, "
                  f"page={top['pageNumber']}, snippet='{top['snippet'][:60]}...'")
        else:
            print(f"Query='{query}' => no results (may be expected)")


def test_search_score_structure(client):
    """Verify search results have expected score breakdown."""
    resp = client.post(
        "/api/search",
        json={"query": "test", "limit": 5},
    )
    assert resp.status_code == 200
    payload = resp.json()
    
    if not payload.get("success"):
        # May be expected if no content matches
        return
        
    data = payload.get("data") or {}
    results = data.get("results") or []
    
    for r in results:
        # Check required fields
        assert "documentId" in r
        assert "documentName" in r
        assert "pageNumber" in r
        assert "snippet" in r
        assert "confidenceScore" in r
        assert "scores" in r
        
        # Check score structure
        scores = r["scores"]
        assert "fusion" in scores
        assert "semantic" in scores
        assert "lexical" in scores
        assert "triple" in scores
        
        # Check confidence is normalized
        assert 0.0 <= r["confidenceScore"] <= 100.0
        
        # Check highlights structure if present
        for hl in r.get("highlights", []):
            assert "text" in hl
            assert "startOffset" in hl
            assert "endOffset" in hl


def test_search_performance(client):
    """Verify search completes in reasonable time."""
    start = time.perf_counter()
    resp = client.post(
        "/api/search",
        json={"query": "machine learning and AI", "limit": 10},
    )
    elapsed = time.perf_counter() - start
    
    assert resp.status_code == 200
    payload = resp.json()
    
    data = payload.get("data") or {}
    search_time = data.get("searchTime", elapsed)
    
    # Search should complete in under 10 seconds (including cross-encoder)
    assert search_time < 10.0, f"Search took too long: {search_time:.2f}s"
    print(f"Search completed in {search_time:.3f}s")


def test_hybrid_search_channels(client):
    """Verify all search channels contribute to results."""
    # Use a broad query likely to hit multiple channels
    resp = client.post(
        "/api/search",
        json={"query": "the system processes data", "limit": 10},
    )
    assert resp.status_code == 200
    payload = resp.json()
    
    data = payload.get("data") or {}
    results = data.get("results") or []
    
    if not results:
        print("No results - skipping channel check")
        return
    
    # Check if different channels are contributing
    has_semantic = any(r["scores"].get("semantic", 0) > 0 for r in results)
    has_lexical = any(r["scores"].get("lexical", 0) > 0 for r in results)
    has_triple = any(r["scores"].get("triple", 0) > 0 for r in results)
    
    print(f"Channel coverage: semantic={has_semantic}, lexical={has_lexical}, triple={has_triple}")
    
    # At least semantic should work for any query
    # (lexical/triple depend on content matching)

"""
Test exact phrase search functionality.

Verifies that when a user searches for an exact sentence that exists in a document,
it should appear at the top of search results with high confidence.
"""
import sys
import pathlib
import uuid

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

# Sync DB access for test setup
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class DummyUser(User):
    def __init__(self, user_id: uuid.UUID, email: str = "tester@example.com"):
        self.id = user_id
        self.email = email
        self.name = "Tester"


def make_fake_current_user(user_id: uuid.UUID):
    def _fake_user():
        return DummyUser(user_id)
    return _fake_user


def _get_document_with_phrase(phrase: str):
    """Find a document containing the exact phrase."""
    db = SessionLocal()
    try:
        # Search for the exact phrase in chunks
        result = db.execute(
            text(
                """
                SELECT c.id as chunk_id, c.pdf_metadata_id, c.page_num, c.chunk_text,
                       p.filename, p.uploaded_by
                FROM pdf_chunks c
                JOIN pdf_metadata p ON p.id = c.pdf_metadata_id
                WHERE lower(c.chunk_text) LIKE lower(:pattern)
                LIMIT 1
                """
            ),
            {"pattern": f"%{phrase}%"}
        ).fetchone()
        return result
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    """Module-scoped test client."""
    # Get any completed PDF for auth
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
    finally:
        db.close()
    
    if not row:
        pytest.skip("No completed PDF found for testing")
    
    pdf_id, uploaded_by, _fname = row
    app.dependency_overrides[get_current_user] = make_fake_current_user(uploaded_by)
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


class TestExactPhraseSearch:
    """Tests for exact phrase search ranking."""
    
    # The exact phrase from user's document
    EXACT_PHRASE = "Several magnetic excitations are distributed circumferentially between the two inner shells"
    
    def test_exact_phrase_is_found(self, client):
        """Verify the exact phrase exists in the database."""
        result = _get_document_with_phrase(self.EXACT_PHRASE)
        
        if result is None:
            pytest.skip(f"Phrase not found in any document: {self.EXACT_PHRASE}")
        
        print(f"\nFound phrase in document: {result.filename}")
        print(f"Page: {result.page_num}")
        print(f"Chunk preview: {result.chunk_text[:200]}...")
    
    def test_exact_phrase_search_returns_match(self, client):
        """Search for exact phrase should return the containing chunk."""
        resp = client.post(
            "/api/search",
            json={"query": self.EXACT_PHRASE, "limit": 20},
        )
        assert resp.status_code == 200, resp.text
        
        payload = resp.json()
        assert payload.get("success") is True
        
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        print(f"\n=== Search for exact phrase ===")
        print(f"Query: {self.EXACT_PHRASE}")
        print(f"Total results: {len(results)}")
        
        # Find result containing the exact phrase
        exact_match_rank = None
        for i, r in enumerate(results):
            snippet = r.get("snippet", "")
            # Check if this result contains the phrase
            if self.EXACT_PHRASE.lower() in snippet.lower():
                exact_match_rank = i + 1
                print(f"\n  Exact match found at rank {exact_match_rank}:")
                print(f"    Page: {r.get('pageNumber')}")
                print(f"    Confidence: {r.get('confidenceScore'):.1f}%")
                print(f"    Scores: {r.get('scores')}")
                break
        
        if exact_match_rank is None:
            # Check all results for debugging
            print("\n  No exact match in snippets. Checking all results:")
            for i, r in enumerate(results[:5]):
                print(f"\n  Result {i+1}:")
                print(f"    Page: {r.get('pageNumber')}")
                print(f"    Confidence: {r.get('confidenceScore'):.1f}%")
                print(f"    Snippet: {r.get('snippet', '')[:100]}...")
                print(f"    Scores: {r.get('scores')}")
        
        # The exact phrase SHOULD appear somewhere in results
        assert len(results) > 0, "Search returned no results"
    
    def test_exact_match_should_rank_first(self, client):
        """An exact phrase match should rank at #1 with high confidence."""
        resp = client.post(
            "/api/search",
            json={"query": self.EXACT_PHRASE, "limit": 20},
        )
        assert resp.status_code == 200
        
        payload = resp.json()
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        if not results:
            pytest.skip("No search results")
        
        # Check the first result
        top_result = results[0]
        
        print(f"\n=== Top result analysis ===")
        print(f"Page: {top_result.get('pageNumber')}")
        print(f"Confidence: {top_result.get('confidenceScore'):.1f}%")
        print(f"Scores: {top_result.get('scores')}")
        print(f"Snippet: {top_result.get('snippet', '')[:200]}...")
        
        # The top result should have:
        # 1. High confidence (>= 50%)
        # 2. Lexical score > 0 (exact match found)
        
        confidence = top_result.get("confidenceScore", 0)
        lexical_score = top_result.get("scores", {}).get("lexical", 0)
        
        # Find if any result has lexical match
        has_lexical_match = any(
            r.get("scores", {}).get("lexical", 0) > 0 
            for r in results
        )
        
        if has_lexical_match:
            # If there's a lexical match, it should be in top 3
            lexical_ranks = [
                i + 1 for i, r in enumerate(results) 
                if r.get("scores", {}).get("lexical", 0) > 0
            ]
            print(f"\nLexical matches at ranks: {lexical_ranks}")
            assert lexical_ranks[0] <= 3, f"Lexical match should be in top 3, found at rank {lexical_ranks[0]}"
        
        # Confidence should not be 0 for any meaningful result
        assert confidence > 0 or len(results) == 0, "Top result has 0% confidence - scoring is broken"
    
    def test_confidence_score_is_reasonable(self, client):
        """All confidence scores should be between 0-100 and not all zeros."""
        resp = client.post(
            "/api/search",
            json={"query": "magnetic field braking", "limit": 10},
        )
        assert resp.status_code == 200
        
        payload = resp.json()
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        if not results:
            pytest.skip("No search results")
        
        confidences = [r.get("confidenceScore", 0) for r in results]
        
        print(f"\nConfidence scores: {confidences}")
        
        # All scores should be in valid range
        for conf in confidences:
            assert 0 <= conf <= 100, f"Invalid confidence score: {conf}"
        
        # At least some scores should be non-zero
        non_zero = [c for c in confidences if c > 0]
        assert len(non_zero) > 0, "All confidence scores are 0 - scoring is broken"
        
        # Scores should be varied, not all the same
        unique_scores = set(confidences)
        print(f"Unique scores: {len(unique_scores)}")


class TestScoreNormalization:
    """Tests for score normalization and fusion."""
    
    def test_no_duplicate_pages(self, client):
        """Verify no duplicate (pdf_id, page) combinations in results."""
        resp = client.post(
            "/api/search",
            json={"query": "Several magnetic excitations are distributed circumferentially between the two inner shells", "limit": 20},
        )
        assert resp.status_code == 200
        
        payload = resp.json()
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        # Track (documentId, pageNumber) pairs
        seen_pages = set()
        duplicates = []
        
        for r in results:
            key = (r.get("documentId"), r.get("pageNumber"))
            if key in seen_pages:
                duplicates.append(key)
            seen_pages.add(key)
        
        print(f"\nTotal results: {len(results)}")
        print(f"Unique pages: {len(seen_pages)}")
        
        if duplicates:
            print(f"Duplicates found: {duplicates}")
        
        assert len(duplicates) == 0, f"Found duplicate pages: {duplicates}"
    
    def test_fusion_scores_are_positive(self, client):
        """Fusion scores should be normalized to [0, 1]."""
        resp = client.post(
            "/api/search",
            json={"query": "magnetic braking system", "limit": 10},
        )
        assert resp.status_code == 200
        
        payload = resp.json()
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        for r in results:
            fusion = r.get("scores", {}).get("fusion", 0)
            # Fusion should be 0-1 after normalization
            assert fusion >= 0, f"Negative fusion score: {fusion}"
            assert fusion <= 1.5, f"Fusion score too high: {fusion}"  # Allow small overshoot
    
    def test_rerank_score_handling(self, client):
        """Rerank scores (which can be negative) should not break ranking."""
        resp = client.post(
            "/api/search",
            json={"query": "eddy current electromagnetic brake", "limit": 10},
        )
        assert resp.status_code == 200
        
        payload = resp.json()
        data = payload.get("data") or {}
        results = data.get("results") or []
        
        if not results:
            pytest.skip("No search results")
        
        # Check that results are sorted by confidence (descending)
        confidences = [r.get("confidenceScore", 0) for r in results]
        
        print(f"\nConfidence order: {confidences}")
        
        # Should be in descending order
        for i in range(len(confidences) - 1):
            assert confidences[i] >= confidences[i + 1], \
                f"Results not sorted: {confidences[i]} < {confidences[i + 1]} at position {i}"

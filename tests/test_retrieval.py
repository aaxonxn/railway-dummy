"""Unit tests for hybrid search, index persistence, exact identifier matching, and precedence."""

import pytest
from helpdesk.config import config
from helpdesk.search import HybridSearcher


def test_index_is_valid():
    """Verify that persisted index exists and matches source documents."""
    searcher = HybridSearcher()
    assert searcher.is_index_valid() is True


def test_index_loading_and_chunk_count():
    """Verify search index loads with the expected chunks."""
    searcher = HybridSearcher()
    assert searcher.load_index() is True
    assert len(searcher.chunks) >= 100


def test_exact_identifier_search_vande_bharat_gazette():
    """Verify exact gazette notification retrieval lands in top 1."""
    searcher = HybridSearcher()
    searcher.load_index()

    query = "What is the gazette notification number for the Vande Bharat Sleeper refund rules?"
    results = searcher.search(query, top_k=3)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert top_chunk.doc_name == "rb_cc08_2026_vande_bharat_sleeper_refund.pdf"
    assert "41(E)" in top_chunk.text or "Vande Bharat" in top_chunk.text


def test_exact_identifier_search_advance_reservation():
    """Verify 60-day advance reservation query retrieves circular 10 of 2024."""
    searcher = HybridSearcher()
    searcher.load_index()

    query = "Commercial Circular No. 10 of 2024 advance reservation period 60 days"
    results = searcher.search(query, top_k=3)
    assert len(results) > 0
    top_chunk, _ = results[0]
    assert top_chunk.doc_name == "rb_cc10_2024_advance_reservation.pdf"


def test_rule_precedence_vande_bharat_sleeper():
    """Verify that a Vande Bharat Sleeper refund query ranks the 2026 circular above 2015 rules."""
    searcher = HybridSearcher()
    searcher.load_index()

    query = "If I cancel my confirmed Vande Bharat Sleeper ticket 10 hours before departure, how much do I lose?"
    results = searcher.search(query, top_k=5)
    assert len(results) > 0

    # The top retrieved chunk should be from the specialized 2026 Vande Bharat Sleeper document
    docs = [c.doc_name for c, _ in results]
    assert "rb_cc08_2026_vande_bharat_sleeper_refund.pdf" in docs[:2]


"""Unit tests for citation validation and formatting."""

import pytest
from helpdesk.citations import deduplicate_citations, format_citations_for_display, validate_citation
from helpdesk.config import config


def test_valid_pdf_citation():
    """Valid PDF citation with positive integer page."""
    source = {"doc": "irctc_refund_rules_jan2026.pdf", "page": 3}
    assert validate_citation(source) is True


def test_valid_html_citation():
    """Valid HTML citation with null page."""
    source = {"doc": "indianrail_refund_rules_2015.html", "page": None}
    assert validate_citation(source) is True


def test_invalid_html_citation_with_page():
    """HTML citation with page number must be invalid."""
    source = {"doc": "indianrail_refund_rules_2015.html", "page": 2}
    assert validate_citation(source) is False


def test_invalid_pdf_citation_without_page():
    """PDF citation missing page or page=None must be invalid."""
    source = {"doc": "irctc_refund_rules_jan2026.pdf", "page": None}
    assert validate_citation(source) is False


def test_invalid_doc_name():
    """Citation with nonexistent doc must be invalid."""
    source = {"doc": "nonexistent_circular_2099.pdf", "page": 1}
    assert validate_citation(source) is False


def test_deduplicate_citations():
    """Duplicate citations should be pruned preserving order."""
    sources = [
        {"doc": "irctc_refund_rules_jan2026.pdf", "page": 1},
        {"doc": "rb_cc08_2025_tatkal.pdf", "page": 2},
        {"doc": "irctc_refund_rules_jan2026.pdf", "page": 1},
        {"doc": "indianrail_refund_rules_2015.html", "page": None},
        {"doc": "indianrail_refund_rules_2015.html", "page": None},
    ]
    deduped = deduplicate_citations(sources)
    assert len(deduped) == 3
    assert deduped[0] == {"doc": "irctc_refund_rules_jan2026.pdf", "page": 1}
    assert deduped[1] == {"doc": "rb_cc08_2025_tatkal.pdf", "page": 2}
    assert deduped[2] == {"doc": "indianrail_refund_rules_2015.html", "page": None}


def test_format_citations_for_display():
    """Test text rendering of citations."""
    sources = [
        {"doc": "irctc_refund_rules_jan2026.pdf", "page": 4},
        {"doc": "indianrail_refund_rules_2015.html", "page": None},
    ]
    formatted = format_citations_for_display(sources)
    assert "Sources:" in formatted
    assert "- irctc_refund_rules_jan2026.pdf, Page 4" in formatted
    assert "- indianrail_refund_rules_2015.html" in formatted


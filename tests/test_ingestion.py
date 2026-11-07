"""Unit tests for document ingestion and text extraction."""

import pytest
from helpdesk.config import config
from helpdesk.ingest import (
    DOCUMENT_METADATA,
    extract_html_document,
    extract_pdf_document,
    extract_table_as_markdown,
    ingest_documents,
)


def test_document_discovery():
    """Verify all 7 official documents are present and recognized."""
    if not config.documents_dir.exists():
        pytest.skip("Documents directory not found")

    docs = sorted([f.name for f in config.documents_dir.iterdir() if f.is_file()])
    assert len(docs) == 7
    assert "indianrail_refund_rules_2015.html" in docs
    assert "irctc_refund_rules_jan2026.pdf" in docs
    assert "pib_2026-03-24_reform_express.html" in docs
    assert "rb_cc08_2025_tatkal.pdf" in docs
    assert "rb_cc08_2026_vande_bharat_sleeper_refund.pdf" in docs
    assert "rb_cc10_2024_advance_reservation.pdf" in docs
    assert "rb_cc10_2025_reservation_charts.pdf" in docs


def test_html_ingestion_and_metadata():
    """Verify HTML extraction preserves metadata and sets page=None."""
    html_path = config.documents_dir / "indianrail_refund_rules_2015.html"
    if not html_path.exists():
        pytest.skip("HTML file not found")

    pages = extract_html_document(html_path)
    assert len(pages) == 1
    page = pages[0]
    assert page.page is None
    assert page.doc_type == "html"
    assert "Indian Railways" in page.authority
    assert "2015" in page.date
    assert len(page.text) > 500
    # Check that table markdown is present
    assert "|" in page.text


def test_pdf_ingestion_and_page_numbers():
    """Verify PDF extraction extracts page-by-page preserving 1-indexed page numbers."""
    pdf_path = config.documents_dir / "irctc_refund_rules_jan2026.pdf"
    if not pdf_path.exists():
        pytest.skip("PDF file not found")

    pages = extract_pdf_document(pdf_path)
    assert len(pages) == 11
    for idx, p in enumerate(pages, 1):
        assert p.page == idx
        assert p.doc_name == "irctc_refund_rules_jan2026.pdf"
        assert p.doc_type == "pdf"
        assert len(p.text) > 100


def test_all_documents_metadata_defined():
    """Verify all 7 documents have defined metadata in DOCUMENT_METADATA."""
    for doc_name, meta in DOCUMENT_METADATA.items():
        assert "title" in meta
        assert "authority" in meta
        assert "date" in meta
        assert "doc_type" in meta
        assert meta["doc_type"] in ["pdf", "html"]


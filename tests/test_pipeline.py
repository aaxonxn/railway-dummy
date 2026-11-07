"""Integration tests for central ask() pipeline and response contract compliance."""

import pytest
from helpdesk.citations import validate_citation
from helpdesk.pipeline import ask


def test_mandatory_response_contract_keys():
    """Verify response dictionary contains exactly the four mandatory keys."""
    res = ask("What is the name of train 12430?")
    required_keys = {"answer", "sources", "sql", "dont_know"}
    assert set(res.keys()) == required_keys

    assert isinstance(res["answer"], str)
    assert isinstance(res["sources"], list)
    assert res["sql"] is None or isinstance(res["sql"], str)
    assert isinstance(res["dont_know"], bool)


def test_mandatory_response_contract_types_on_abstain():
    """Verify contract types when abstaining."""
    res = ask("What is the fare for 3AC?")
    required_keys = {"answer", "sources", "sql", "dont_know"}
    assert set(res.keys()) == required_keys

    assert isinstance(res["answer"], str)
    assert res["sources"] == []
    assert res["sql"] is None
    assert res["dont_know"] is True


def test_pipeline_sql_route():
    """Verify end-to-end SQL query returns train name, sql statement, and no sources."""
    res = ask("What is the name of train 12430?")
    assert res["dont_know"] is False
    assert "Rajdhani" in res["answer"]
    assert res["sql"] is not None
    assert "12430" in res["sql"]
    assert res["sources"] == []


def test_pipeline_sources_validation():
    """Verify that any sources returned in RAG answers are strictly valid."""
    res = ask("What is the gazette notification number for the Vande Bharat Sleeper refund rules?")
    if not res["dont_know"] and res["sources"]:
        for source in res["sources"]:
            assert validate_citation(source) is True


def test_pipeline_route_jaipur_to_udaipur():
    """Verify end-to-end route search from Jaipur (JP) to Udaipur City (UDZ)."""
    res = ask("Find trains from Jaipur (JP) to Udaipur City (UDZ).")
    assert res["dont_know"] is False
    assert res["sql"] is not None
    assert "stops" in res["sql"].lower()
    assert res["sources"] == []

    ans = res["answer"]
    # Check train numbers
    assert "12315" in ans or "Ananya" in ans
    assert "12965" in ans or "Gwalior Udaipur" in ans
    # Check departure and arrival times from timetable
    assert "17:20" in ans
    assert "22:30" in ans


def test_pipeline_hybrid_c15_regression():
    """Regression test for compound question C15 requiring both SQL and document RAG."""
    q = "When does train 12430 depart, and what is the flat cancellation charge if a confirmed AC 3-tier ticket is cancelled more than 48 hours before departure?"
    res = ask(q)
    assert res["dont_know"] is False
    assert res["sql"] is not None
    assert "12430" in res["sql"]
    assert res["sources"] != []

    # Verify cited document includes IRCTC refund rules
    doc_names = {s["doc"] for s in res["sources"]}
    assert "irctc_refund_rules_jan2026.pdf" in doc_names

    # Verify both timetable fact (20:50) and refund fact (180) are in the answer
    ans = res["answer"]
    assert "20:50" in ans
    assert "180" in ans


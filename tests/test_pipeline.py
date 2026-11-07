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


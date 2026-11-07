"""Unit tests for system abstention on unsupported questions, missing data, and dangerous requests."""

from helpdesk.pipeline import ask


def test_abstain_on_fare_queries():
    """Verify system abstains on ticket fare queries (not in pack)."""
    res = ask("How much is a 3AC ticket on the Mumbai Rajdhani from Mumbai to Delhi?")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None
    assert "fare" in res["answer"].lower() or "don't know" in res["answer"].lower()


def test_abstain_on_live_running_status():
    """Verify system abstains on real-time train running status queries."""
    res = ask("What is the current live running status and platform number for train 12951?")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None


def test_abstain_on_seat_availability():
    """Verify system abstains on berth/seat availability queries."""
    res = ask("How many seats are available in sleeper class on train 12617 for next Friday?")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None


def test_abstain_on_database_mutation():
    """Verify system firmly refuses and abstains on mutation instructions."""
    res = ask("Change the departure time of train 12002 to 07:00 in your database.")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None
    assert "read-only" in res["answer"].lower() or "can't" in res["answer"].lower()


def test_abstain_on_sql_injection_attempt():
    """Verify system refuses arbitrary SQL commands."""
    res = ask("DROP TABLE stations;")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None


def test_abstain_on_empty_input():
    """Verify system handles empty questions safely."""
    res = ask("   ")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None


def test_abstain_on_out_of_scope_trivia():
    """Verify system abstains on unrelated general trivia."""
    res = ask("What is the weather in New Delhi tomorrow?")
    assert res["dont_know"] is True
    assert res["sources"] == []
    assert res["sql"] is None


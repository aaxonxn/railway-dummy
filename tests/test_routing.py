"""Unit tests for question routing logic."""

import json
from pathlib import Path
import pytest

from helpdesk.config import config
from helpdesk.routing import Route, classify_question


def test_routing_sample_questions():
    """Verify that all 10 sample questions route to their expected category."""
    sample_file = config.data_dir / "questions" / "sample_questions.json"
    if not sample_file.exists():
        pytest.skip("Sample questions file not found")

    with open(sample_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    expected_routes = {
        "S01": Route.RAG,       # Vande Bharat Sleeper refund gazette notification
        "S02": Route.SQL,       # Train 12430 name
        "S03": Route.RAG,       # 60-day booking limit on Taj Express
        "S04": Route.SQL,       # Trains from JP to UDZ
        "S05": Route.ABSTAIN,   # 3AC fare on Mumbai Rajdhani (no fare tables)
        "S06": Route.RAG,       # Waitlisted sleeper cancellation clerkage
        "S07": Route.HYBRID,    # Bhopal Shatabdi departure + cancellation charge
        "S08": Route.RAG,       # Vande Bharat Sleeper 10 hours before departure
        "S09": Route.SQL,       # Count Rajdhani trains
        "S10": Route.ABSTAIN,   # Mutation: Change departure time of train 12002
    }

    for item in questions:
        q_id = item["id"]
        q_text = item["question"]
        route, _ = classify_question(q_text)
        assert route == expected_routes[q_id], f"Question {q_id} failed: expected {expected_routes[q_id]}, got {route} for '{q_text}'"


def test_routing_abstention_cases():
    """Verify that unsupported queries and mutations abstain."""
    # Fares
    route, reason = classify_question("What is the fare of 12951 from Mumbai to Delhi?")
    assert route == Route.ABSTAIN

    # Weather
    route, reason = classify_question("What is the weather in New Delhi tomorrow?")
    assert route == Route.ABSTAIN

    # Mutations
    route, reason = classify_question("DELETE FROM trains WHERE number = '12002';")
    assert route == Route.ABSTAIN

    route, reason = classify_question("Modify the arrival time of Rajdhani Express")
    assert route == Route.ABSTAIN


def test_routing_sql_cases():
    """Verify timetable queries are routed to SQL."""
    route, _ = classify_question("What time does train 12951 leave Mumbai?")
    assert route == Route.SQL

    route, _ = classify_question("Which trains run between New Delhi and Howrah?")
    assert route == Route.SQL


def test_routing_rag_cases():
    """Verify policy questions are routed to RAG."""
    route, _ = classify_question("What is the cancellation fee for a confirmed AC 2-tier ticket?")
    assert route == Route.RAG

    route, _ = classify_question("Is Aadhaar verification required for Tatkal ticket booking?")
    assert route == Route.RAG

    route, _ = classify_question("When are first reservation charts prepared?")
    assert route == Route.RAG


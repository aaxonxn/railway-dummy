"""Unit tests for SQLite timetable query engine and security validations."""

import pytest
from helpdesk.config import config
from helpdesk.sql import execute_sql, validate_sql


def test_sql_validation_valid_select():
    """Verify that legitimate SELECT queries pass validation."""
    query = "SELECT number, name FROM trains WHERE number = '12430'"
    is_valid, validated, err = validate_sql(query)
    assert is_valid is True
    assert err is None
    assert "LIMIT" in validated


def test_sql_validation_blocks_mutations():
    """Verify that INSERT, UPDATE, DELETE, DROP, ALTER are firmly rejected."""
    bad_queries = [
        "UPDATE trains SET departure = '07:00' WHERE number = '12002'",
        "DELETE FROM trains WHERE number = '12430'",
        "INSERT INTO stations (code, name) VALUES ('TEST', 'Test Station')",
        "DROP TABLE trains",
        "ALTER TABLE stations ADD COLUMN test TEXT",
        "PRAGMA table_info(trains)",
        "ATTACH DATABASE 'evil.db' AS evil",
    ]
    for q in bad_queries:
        is_valid, _, err = validate_sql(q)
        assert is_valid is False
        assert err is not None


def test_sql_validation_blocks_multi_statements():
    """Verify that chained statements with semicolon are rejected."""
    bad_queries = [
        "SELECT 1; DROP TABLE trains;",
        "SELECT * FROM stations; SELECT * FROM trains;",
    ]
    for q in bad_queries:
        is_valid, _, err = validate_sql(q)
        assert is_valid is False
        assert "Multiple SQL statements" in err


def test_sql_validation_blocks_comments():
    """Verify that comments that could hide injections are rejected."""
    bad_queries = [
        "SELECT * FROM trains WHERE number = '12002' -- comment",
        "SELECT * FROM trains /* block comment */",
    ]
    for q in bad_queries:
        is_valid, _, err = validate_sql(q)
        assert is_valid is False
        assert "SQL comments are not permitted" in err


def test_sql_validation_blocks_unknown_tables():
    """Verify queries targeting nonexistent or unauthorized tables are rejected."""
    query = "SELECT * FROM users_private_table"
    is_valid, _, err = validate_sql(query)
    assert is_valid is False
    assert "not part of the timetable schema" in err


def test_sql_execution_read_only():
    """Verify safe execution of timetable queries."""
    if not config.database_path.exists():
        pytest.skip("Timetable database not found")

    ok, rows, q, err = execute_sql("SELECT number, name FROM trains WHERE number = '12430';")
    assert ok is True
    assert len(rows) == 1
    assert rows[0]["number"] == "12430"
    assert "Rajdhani" in rows[0]["name"]


def test_sql_execution_count():
    """Verify aggregation queries execute correctly."""
    if not config.database_path.exists():
        pytest.skip("Timetable database not found")

    ok, rows, q, err = execute_sql("SELECT COUNT(*) as count FROM trains WHERE type_code = 'Raj';")
    assert ok is True
    assert len(rows) == 1
    assert rows[0]["count"] == 48


def test_sql_execution_join_stops():
    """Verify joining stops view works as documented in schema.md."""
    if not config.database_path.exists():
        pytest.skip("Timetable database not found")

    q = (
        "SELECT t.number, t.name, a.departure, b.arrival "
        "FROM stops a "
        "JOIN stops b ON b.train_number = a.train_number AND b.stop_sequence > a.stop_sequence "
        "JOIN trains t ON t.number = a.train_number "
        "WHERE a.station_code = 'JP' AND b.station_code = 'UDZ' "
        "ORDER BY a.departure;"
    )
    ok, rows, _, err = execute_sql(q)
    assert ok is True
    assert len(rows) >= 2


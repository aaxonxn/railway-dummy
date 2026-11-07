"""SQLite Timetable Query Engine with strict read-only security, validation, and NL-to-SQL generation."""

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from helpdesk.config import config
from helpdesk.logging_config import logger

VALID_TABLES = {"stations", "train_types", "trains", "schedules", "stops"}

FORBIDDEN_KEYWORDS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b",
    r"\bEXEC\b",
    r"\bVACUUM\b",
    r"\bREINDEX\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bINTO\s+OUTFILE\b",
    r"\bLOAD_FILE\b",
]

SCHEMA_DOCUMENTATION = """
Database Schema (Snapshot from 2016):

1. stations (code TEXT PRIMARY KEY, name TEXT, state TEXT, zone TEXT, address TEXT, latitude REAL, longitude REAL)
   - code: e.g. 'NDLS', 'SBC', 'JP', 'UDZ'
   - name: Station name, e.g. 'NEW DELHI', 'Kalka' (Use LIKE for partial station name matching)

2. train_types (type_code TEXT PRIMARY KEY, meaning TEXT)
   - e.g. ('Raj', 'Rajdhani Express'), ('Shtb', 'Shatabdi Express')

3. trains (number TEXT PRIMARY KEY, name TEXT, type_code TEXT, zone TEXT, from_station_code TEXT, to_station_code TEXT, departure TEXT, arrival TEXT, duration_min INTEGER, distance_km INTEGER, return_train TEXT, has_1a INTEGER, has_2a INTEGER, has_3a INTEGER, has_sl INTEGER, has_cc INTEGER, has_fc INTEGER)
   - number: 5-digit string, e.g. '12951', '12430'
   - times: 'HH:MM' 24-hour format

4. schedules (train_number TEXT, stop_sequence INTEGER, station_code TEXT, day INTEGER, arrival TEXT, departure TEXT, halt_min INTEGER, is_halt INTEGER, PRIMARY KEY (train_number, stop_sequence))
   - includes stations a train only passes through without stopping!

5. stops (VIEW):
   - Only rows where train actually halts (is_halt = 1).
   - Columns: train_number, stop_sequence, station_code, day, arrival, departure, halt_min, is_halt.
   - ALWAYS USE 'stops' view for routes, stops, and train search between stations.

IMPORTANT QUERY PATTERNS:
- Trains from A to B:
  SELECT t.number, t.name, a.departure, b.arrival
  FROM stops a
  JOIN stops b ON b.train_number = a.train_number AND b.stop_sequence > a.stop_sequence
  JOIN trains t ON t.number = a.train_number
  WHERE a.station_code = 'JP' AND b.station_code = 'UDZ'
  ORDER BY a.departure;

- Train details by number:
  SELECT number, name FROM trains WHERE number = '12430';

- Counting trains of a type:
  SELECT COUNT(*) FROM trains WHERE type_code = 'Raj';

- Train departure time:
  SELECT departure FROM schedules WHERE train_number = '12002' AND station_code = 'NDLS';
"""


def authorizer_callback(action: int, arg1: Any, arg2: Any, db_name: Any, trigger_name: Any) -> int:
    """SQLite authorizer hook to forbid any mutation or dangerous operation."""
    # Allow reading columns
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK
    # Allow SELECT statements
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    # Allow standard SQL functions
    if action == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_OK
    # Deny all other actions
    return sqlite3.SQLITE_DENY


def validate_sql(query: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate SQL statement for security and correctness.
    Returns (is_valid, sanitized_query_or_error, error_message).
    """
    if not query or not query.strip():
        return False, "", "Empty query"

    cleaned = query.strip()

    # Disallow SQL comments that could disguise injected commands
    if "--" in cleaned or "/*" in cleaned:
        return False, "", "SQL comments are not permitted."

    # Check for multiple statements separated by semicolon
    # Strip trailing semicolon if single statement
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()

    if ";" in cleaned:
        return False, "", "Multiple SQL statements are not permitted."

    # Must start with SELECT or WITH
    upper_query = cleaned.upper()
    if not (upper_query.startswith("SELECT") or upper_query.startswith("WITH")):
        return False, "", "Only read-only SELECT queries are permitted."

    # Check for forbidden keywords
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            match = re.search(pattern, cleaned, re.IGNORECASE).group(0)
            return False, "", f"Operation '{match}' is forbidden on the read-only timetable database."

    # Check that referenced tables belong to the valid schema
    # Simple regex check for FROM and JOIN table names
    table_candidates = re.findall(r"(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", cleaned, re.IGNORECASE)
    for tbl in table_candidates:
        if tbl.lower() not in VALID_TABLES:
            return False, "", f"Table '{tbl}' is not part of the timetable schema."

    # Enforce result row limit if not specified
    if not re.search(r"\bLIMIT\s+\d+", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT {config.sql_max_rows}"

    return True, cleaned, None


def execute_sql(query: str, db_path: Optional[Path] = None) -> Tuple[bool, List[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Execute a validated SELECT query against the read-only SQLite database.
    Returns (success, rows, executed_query, error_message).
    """
    is_valid, validated_query, err = validate_sql(query)
    if not is_valid:
        logger.warning("SQL validation failed for query: %s | Error: %s", query, err)
        return False, [], None, err

    target_db = db_path or config.database_path
    if not target_db.exists():
        msg = f"Database file not found: {target_db}"
        logger.error(msg)
        return False, [], None, msg

    # Connect strictly in read-only mode using URI
    uri_path = f"file:{target_db.resolve()}?mode=ro"

    try:
        con = sqlite3.connect(uri_path, uri=True, timeout=config.sql_timeout_sec)
        # Apply authorizer hook
        con.set_authorizer(authorizer_callback)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(validated_query)
        raw_rows = cur.fetchall()
        rows = [dict(r) for r in raw_rows]
        con.close()
        return True, rows, validated_query, None
    except sqlite3.DatabaseError as e:
        logger.error("SQLite execution error on query '%s': %s", validated_query, e)
        return False, [], validated_query, str(e)
    except Exception as e:
        logger.error("Unexpected error executing query '%s': %s", validated_query, e)
        return False, [], validated_query, str(e)


def format_sql_results_as_text(rows: List[Dict[str, Any]]) -> str:
    """Format query result rows into clean passenger-readable tabular or bullet text."""
    if not rows:
        return "No matching timetable records were found in the database."

    if len(rows) == 1 and len(rows[0]) == 1:
        # Single scalar value (like COUNT)
        key, val = list(rows[0].items())[0]
        return f"{key}: {val}"

    lines = []
    for i, row in enumerate(rows, 1):
        row_parts = [f"{k}: {v}" for k, v in row.items()]
        lines.append(f"{i}. " + ", ".join(row_parts))

    return "\n".join(lines)


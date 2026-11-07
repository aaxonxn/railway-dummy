"""Utility functions for text processing, normalization, and pattern matching."""

import json
import re
from typing import Any, List, Optional, Set


def normalize_whitespace(text: str) -> str:
    """Normalize irregular whitespace, consecutive newlines, and tabs."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_train_numbers(text: str) -> List[str]:
    """Extract candidate 5-digit train numbers or slip train numbers from text."""
    matches = re.findall(r"\b(\d{5}(?:-Slip)?)\b", text)
    # Deduplicate preserving order
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def extract_circular_numbers(text: str) -> List[str]:
    """Extract Commercial Circular references like '10 of 2024', '08 of 2025', '8 of 2026'."""
    patterns = [
        r"Commercial\s+Circular\s+(?:No\.?\s*)?(\d{1,2}\s+of\s+\d{4})",
        r"CC\s*(?:No\.?\s*)?(\d{1,2}\s+of\s+\d{4})",
        r"(\d{1,2}\s+of\s+\d{4})",
    ]
    results = []
    seen = set()
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            val = m.group(1).strip()
            if val not in seen:
                seen.add(val)
                results.append(val)
    return results


def extract_gazette_notifications(text: str) -> List[str]:
    """Extract Gazette notifications like 'G.S.R. 41(E)'."""
    matches = re.findall(r"G\.?S\.?R\.?\s*\d+\s*\([A-Z]\)", text, re.IGNORECASE)
    seen = set()
    result = []
    for m in matches:
        norm = re.sub(r"\s+", " ", m.upper().strip())
        if norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def extract_station_codes(text: str) -> List[str]:
    """Extract candidate station codes like NDLS, SBC, JP, UDZ, BCT, CST."""
    # Look for capitalized 2-5 letter codes in parentheses or standalone
    matches = re.findall(r"\b([A-Z]{2,5})\b", text)
    common_codes = {
        "NDLS", "SBC", "JP", "UDZ", "MMCT", "BCT", "CSMT", "CST", "HWH", "MAS",
        "BPL", "AGC", "GWL", "NZM", "CNB", "BSB", "PNBE", "ADI", "PUNE", "LKO"
    }
    return [m for m in matches if m in common_codes]


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder handling Path and special objects."""

    def default(self, o: Any) -> Any:
        if hasattr(o, "__fspath__"):
            return str(o)
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return super().default(o)


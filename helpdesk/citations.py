"""Citation validation and extraction module."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from helpdesk.config import config
from helpdesk.logging_config import logger


def validate_citation(source: Dict[str, Any], documents_dir: Optional[Path] = None) -> bool:
    """
    Validate that a source citation is well-formed:
    - Contains 'doc' (string matching an actual document file)
    - Contains 'page' (integer for PDF, None for HTML)
    """
    if not isinstance(source, dict):
        return False

    doc = source.get("doc")
    page = source.get("page")

    if not isinstance(doc, str) or not doc.strip():
        return False

    target_dir = documents_dir or config.documents_dir
    doc_path = target_dir / doc
    # Check if doc exists in pack (if documents_dir is present)
    if target_dir.exists() and not doc_path.is_file():
        logger.warning("Cited document does not exist: %s", doc)
        return False

    if doc.lower().endswith(".html") or doc.lower().endswith(".htm"):
        if page is not None:
            logger.warning("HTML citation must have page: null, got: %s", page)
            return False
    elif doc.lower().endswith(".pdf"):
        if not (isinstance(page, int) and page >= 1):
            logger.warning("PDF citation must have positive integer page, got: %s", page)
            return False

    return True


def deduplicate_citations(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate citations preserving original order."""
    seen = set()
    deduped = []
    for s in sources:
        key = (s.get("doc"), s.get("page"))
        if key not in seen:
            seen.add(key)
            deduped.append({"doc": s.get("doc"), "page": s.get("page")})
    return deduped


def format_citations_for_display(sources: List[Dict[str, Any]]) -> str:
    """Format citations into a readable string for terminal output."""
    if not sources:
        return ""
    lines = ["Sources:"]
    for s in sources:
        doc = s.get("doc")
        page = s.get("page")
        if page is None:
            lines.append(f"- {doc}")
        else:
            lines.append(f"- {doc}, Page {page}")
    return "\n".join(lines)


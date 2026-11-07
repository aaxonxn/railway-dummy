"""Core execution pipeline coordinating routing, retrieval, SQL, and answer synthesis."""

from typing import Any, Dict, List, Optional
from helpdesk.answer import AnswerGenerator
from helpdesk.citations import validate_citation
from helpdesk.config import config
from helpdesk.logging_config import logger
from helpdesk.routing import Route, classify_question
from helpdesk.search import HybridSearcher

# Singleton instances
_SEARCHER = None
_GENERATOR = None


def get_searcher() -> HybridSearcher:
    """Retrieve or initialize the hybrid searcher."""
    global _SEARCHER
    if _SEARCHER is None:
        _SEARCHER = HybridSearcher()
        if not _SEARCHER.load_index():
            logger.warning("Search index not found in %s; searching will fail until built.", config.index_dir)
    return _SEARCHER


def get_generator() -> AnswerGenerator:
    """Retrieve or initialize the answer generator."""
    global _GENERATOR
    if _GENERATOR is None:
        _GENERATOR = AnswerGenerator()
    return _GENERATOR


def ask(question: str) -> Dict[str, Any]:
    """
    Central entry point for the Railway Passenger Help Desk.

    Returns a dictionary conforming strictly to the mandatory response contract:
    {
        "answer": str,
        "sources": List[{"doc": str, "page": Optional[int]}],
        "sql": Optional[str],
        "dont_know": bool
    }
    """
    logger.info("Received passenger question: %s", question)

    # Validate input
    if not question or not question.strip():
        return {
            "answer": "Please ask a question regarding railway policies, refunds, or timetables.",
            "sources": [],
            "sql": None,
            "dont_know": True,
        }

    q = question.strip()
    route, reason = classify_question(q)
    logger.info("Classified route: %s (%s)", route.value, reason)

    # Route 1: Abstention / Unsupported / Mutation
    if route == Route.ABSTAIN:
        return {
            "answer": reason,
            "sources": [],
            "sql": None,
            "dont_know": True,
        }

    generator = get_generator()

    # Route 2: Timetable SQL Query
    if route == Route.SQL:
        try:
            ans_text, executed_sql, dont_know = generator.generate_sql_answer(q)
            return {
                "answer": ans_text,
                "sources": [],
                "sql": executed_sql,
                "dont_know": dont_know,
            }
        except Exception as e:
            logger.error("SQL route failure: %s", e)
            return {
                "answer": "I could not find matching records in the timetable database.",
                "sources": [],
                "sql": None,
                "dont_know": True,
            }

    searcher = get_searcher()

    # Route 3: Hybrid (SQL + Document RAG)
    if route == Route.HYBRID:
        try:
            candidates = searcher.search(q, top_k=config.retrieval_top_k)
            retrieved_chunks = [c for c, _ in candidates]
            ans_text, sources, executed_sql, dont_know = generator.generate_hybrid_answer(
                question=q, chunks=retrieved_chunks
            )
            # Filter valid citations
            valid_sources = [s for s in sources if validate_citation(s)]
            return {
                "answer": ans_text,
                "sources": valid_sources,
                "sql": executed_sql,
                "dont_know": dont_know,
            }
        except Exception as e:
            logger.error("Hybrid route failure: %s", e)
            return {
                "answer": "I could not find sufficient information to answer both the timetable and policy aspects.",
                "sources": [],
                "sql": None,
                "dont_know": True,
            }

    # Route 4: Document RAG
    if route == Route.RAG:
        try:
            candidates = searcher.search(q, top_k=config.retrieval_top_k)
            retrieved_chunks = [c for c, _ in candidates]
            ans_text, sources, dont_know = generator.generate_rag_answer(
                question=q, chunks=retrieved_chunks
            )
            valid_sources = [s for s in sources if validate_citation(s)]
            return {
                "answer": ans_text,
                "sources": valid_sources,
                "sql": None,
                "dont_know": dont_know,
            }
        except Exception as e:
            logger.error("RAG route failure: %s", e)
            return {
                "answer": "I could not find sufficient information in the supplied railway documents to answer this question reliably.",
                "sources": [],
                "sql": None,
                "dont_know": True,
            }

    # Fallback default
    return {
        "answer": "I could not find sufficient information in the supplied railway documents to answer this question reliably.",
        "sources": [],
        "sql": None,
        "dont_know": True,
    }


"""Comprehensive evaluation metrics and test runner for Railway Passenger Help Desk."""

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from helpdesk.config import config
from helpdesk.logging_config import logger
from helpdesk.pipeline import ask
from helpdesk.routing import Route, classify_question
from helpdesk.search import HybridSearcher


@dataclass
class EvalMetrics:
    """Summary metrics container."""
    total_questions: int = 0
    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hit_at_5: float = 0.0
    mrr: float = 0.0
    routing_accuracy: float = 0.0
    sql_execution_success: float = 0.0
    citation_precision: float = 0.0
    abstention_accuracy: float = 0.0
    overall_accuracy: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_retrieval(questions: List[Dict[str, Any]], searcher: Optional[HybridSearcher] = None) -> Dict[str, float]:
    """
    Compute Hit@1, Hit@3, Hit@5, and MRR for questions that require document retrieval.
    """
    search = searcher or HybridSearcher()
    if not search.chunks:
        search.load_index()

    rag_questions = [q for q in questions if q.get("expected_sources")]
    if not rag_questions:
        return {"hit@1": 0.0, "hit@3": 0.0, "hit@5": 0.0, "mrr": 0.0, "evaluated": 0}

    hits_1 = 0
    hits_3 = 0
    hits_5 = 0
    reciprocal_ranks = []

    for item in rag_questions:
        q_text = item["question"]
        expected_sources = item.get("expected_sources", [])
        expected_docs = {s["doc"] for s in expected_sources}

        try:
            results = search.search(q_text, top_k=5)
        except Exception as e:
            logger.error("Search failed during evaluation: %s", e)
            results = []

        found_rank = None
        for rank, (chunk, _) in enumerate(results, 1):
            if chunk.doc_name in expected_docs:
                found_rank = rank
                break

        if found_rank == 1:
            hits_1 += 1
        if found_rank is not None and found_rank <= 3:
            hits_3 += 1
        if found_rank is not None and found_rank <= 5:
            hits_5 += 1

        if found_rank is not None:
            reciprocal_ranks.append(1.0 / found_rank)
        else:
            reciprocal_ranks.append(0.0)

    n = len(rag_questions)
    return {
        "hit@1": hits_1 / n,
        "hit@3": hits_3 / n,
        "hit@5": hits_5 / n,
        "mrr": sum(reciprocal_ranks) / n,
        "evaluated": n,
    }


def evaluate_routing(questions: List[Dict[str, Any]]) -> Dict[str, float]:
    """Evaluate question routing classification accuracy."""
    correct = 0
    total = len(questions)

    for item in questions:
        q_text = item["question"]
        route, _ = classify_question(q_text)

        # Determine expected route from item attributes
        if item.get("expected_dont_know", False):
            expected = Route.ABSTAIN
        elif item.get("expected_sql") and item.get("expected_sources"):
            expected = Route.HYBRID
        elif item.get("expected_sql"):
            expected = Route.SQL
        else:
            expected = Route.RAG

        if route == expected:
            correct += 1

    return {
        "routing_accuracy": correct / total if total > 0 else 0.0,
        "correct": correct,
        "total": total,
    }


def evaluate_end_to_end(questions: List[Dict[str, Any]]) -> Tuple[EvalMetrics, List[Dict[str, Any]]]:
    """
    Run end-to-end evaluation over test questions.
    Computes retrieval, routing, citation, abstention, and SQL accuracy.
    """
    searcher = HybridSearcher()
    searcher.load_index()

    retrieval_res = evaluate_retrieval(questions, searcher)
    routing_res = evaluate_routing(questions)

    detailed_results = []
    sql_attempts = 0
    sql_success = 0
    citation_matches = 0
    citation_attempts = 0
    abstention_matches = 0
    abstention_attempts = 0

    for item in questions:
        q_id = item.get("id", "Q")
        q_text = item["question"]
        expected_dont_know = item.get("expected_dont_know", False)
        expected_sources = item.get("expected_sources", [])
        expected_sql = item.get("expected_sql")

        res = ask(q_text)

        # Evaluate abstention
        if expected_dont_know:
            abstention_attempts += 1
            if res.get("dont_know") is True:
                abstention_matches += 1

        # Evaluate citations
        if expected_sources:
            citation_attempts += 1
            retrieved_docs = {s.get("doc") for s in res.get("sources", [])}
            exp_docs = {s["doc"] for s in expected_sources}
            if exp_docs.intersection(retrieved_docs):
                citation_matches += 1

        # Evaluate SQL
        if expected_sql:
            sql_attempts += 1
            if res.get("sql") is not None and not res.get("dont_know"):
                sql_success += 1

        detailed_results.append({
            "id": q_id,
            "question": q_text,
            "response": res,
            "expected_dont_know": expected_dont_know,
            "expected_sources": expected_sources,
        })

    metrics = EvalMetrics(
        total_questions=len(questions),
        hit_at_1=retrieval_res["hit@1"],
        hit_at_3=retrieval_res["hit@3"],
        hit_at_5=retrieval_res["hit@5"],
        mrr=retrieval_res["mrr"],
        routing_accuracy=routing_res["routing_accuracy"],
        sql_execution_success=sql_success / sql_attempts if sql_attempts > 0 else 1.0,
        citation_precision=citation_matches / citation_attempts if citation_attempts > 0 else 1.0,
        abstention_accuracy=abstention_matches / abstention_attempts if abstention_attempts > 0 else 1.0,
        overall_accuracy=(
            routing_res["routing_accuracy"] + retrieval_res["hit@5"] + (sql_success / sql_attempts if sql_attempts > 0 else 1.0)
        ) / 3.0,
    )

    return metrics, detailed_results


"""Standalone evaluation script to measure retrieval, routing, SQL, and answer quality."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpdesk.config import config
from helpdesk.evaluation import evaluate_end_to_end, evaluate_retrieval, evaluate_routing
from helpdesk.search import HybridSearcher


def main():
    parser = argparse.ArgumentParser(description="Evaluate Railway Passenger Help Desk system")
    parser.add_argument(
        "--testset",
        type=str,
        default=str(config.project_root / "eval" / "test_set.json"),
        help="Path to evaluation question set JSON",
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Run fast retrieval-only evaluation (Hit@K, MRR) without calling LLM",
    )
    args = parser.parse_args()

    testset_path = Path(args.testset)
    if not testset_path.exists():
        print(f"ERROR: Testset file not found: {testset_path}")
        sys.exit(1)

    with open(testset_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Loaded {len(questions)} test questions from {testset_path.name}")

    if args.retrieval_only:
        print("\n--- RETRIEVAL EVALUATION (Dense + BM25 + RRF) ---")
        searcher = HybridSearcher()
        searcher.load_index()
        retrieval_metrics = evaluate_retrieval(questions, searcher)
        routing_metrics = evaluate_routing(questions)

        print(f"Evaluated Questions : {retrieval_metrics['evaluated']}")
        print(f"Hit@1               : {retrieval_metrics['hit@1'] * 100:.1f}%")
        print(f"Hit@3               : {retrieval_metrics['hit@3'] * 100:.1f}%")
        print(f"Hit@5               : {retrieval_metrics['hit@5'] * 100:.1f}%")
        print(f"MRR                 : {retrieval_metrics['mrr']:.4f}")
        print(f"Routing Accuracy    : {routing_metrics['routing_accuracy'] * 100:.1f}%")
        return

    print("\n--- END-TO-END SYSTEM EVALUATION ---")
    metrics, details = evaluate_end_to_end(questions)

    print("\n==================================================")
    print("           EVALUATION METRICS SUMMARY             ")
    print("==================================================")
    print(f"Total Test Questions     : {metrics.total_questions}")
    print(f"Retrieval Hit@1          : {metrics.hit_at_1 * 100:.1f}%")
    print(f"Retrieval Hit@3          : {metrics.hit_at_3 * 100:.1f}%")
    print(f"Retrieval Hit@5          : {metrics.hit_at_5 * 100:.1f}%")
    print(f"Retrieval MRR            : {metrics.mrr:.4f}")
    print(f"Routing Accuracy         : {metrics.routing_accuracy * 100:.1f}%")
    print(f"Citation Precision       : {metrics.citation_precision * 100:.1f}%")
    print(f"Abstention Accuracy      : {metrics.abstention_accuracy * 100:.1f}%")
    print(f"SQL Execution Success    : {metrics.sql_execution_success * 100:.1f}%")
    print(f"Overall Accuracy         : {metrics.overall_accuracy * 100:.1f}%")
    print("==================================================")


if __name__ == "__main__":
    main()


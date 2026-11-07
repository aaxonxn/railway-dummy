"""Batch execution script to evaluate question sets and produce formatted result JSON."""

import json
import sys
import time
from pathlib import Path
from helpdesk import ask
from helpdesk.logging_config import logger


def run_questions(input_file: Path, output_file: Path) -> None:
    """Read questions from input_file, evaluate each through ask(), and write output_file."""
    if not input_file.exists():
        print(f"ERROR: Input questions file not found: {input_file}")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Loaded {len(questions)} questions from {input_file.name}")
    results = []

    start_time = time.time()
    for idx, item in enumerate(questions, 1):
        q_id = item.get("id", f"Q{idx}")
        q_text = item.get("question", "")

        print(f"[{idx}/{len(questions)}] Processing {q_id}: '{q_text[:60]}...'")
        t0 = time.time()
        try:
            res = ask(q_text)
        except Exception as e:
            logger.error("Error processing question %s: %s", q_id, e)
            res = {
                "answer": "An unexpected error occurred while processing this question.",
                "sources": [],
                "sql": None,
                "dont_know": True,
            }

        elapsed = time.time() - t0

        record = {
            "id": q_id,
            "question": q_text,
            "answer": res.get("answer", ""),
            "sources": res.get("sources", []),
            "sql": res.get("sql"),
            "dont_know": res.get("dont_know", False),
        }
        results.append(record)
        print(f"    Done in {elapsed:.2f}s | dont_know: {record['dont_know']} | sources: {len(record['sources'])}")

    total_time = time.time() - start_time
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nCompleted {len(questions)} questions in {total_time:.2f}s.")
    print(f"Results written to: {output_file}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python run_questions.py <questions.json> <results.json>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    run_questions(input_path, output_path)


if __name__ == "__main__":
    main()


"""CLI script to build, check, and inspect the hybrid retrieval index."""

import argparse
import json
import sys
from pathlib import Path

from helpdesk.chunking import chunk_all_pages
from helpdesk.config import config
from helpdesk.ingest import ingest_documents
from helpdesk.logging_config import logger
from helpdesk.search import HybridSearcher


def main():
    parser = argparse.ArgumentParser(description="Railway Passenger Help Desk - Index Builder")
    parser.add_argument("--force", action="store_true", help="Force full rebuild of the index")
    parser.add_argument("--check", action="store_true", help="Verify index integrity and manifest")
    parser.add_argument("--stats", action="store_true", help="Display index statistics and metadata")
    args = parser.parse_args()

    searcher = HybridSearcher()

    if args.check:
        print("Checking index integrity...")
        valid = searcher.is_index_valid()
        if valid:
            print("SUCCESS: Index exists, is valid, and matches all source documents.")
            sys.exit(0)
        else:
            print("WARNING: Index is missing, corrupted, or out-of-date with source documents.")
            sys.exit(1)

    if args.stats:
        meta_file = config.index_dir / "metadata.json"
        if not meta_file.exists():
            print("ERROR: Index has not been built yet. Run 'python build_index.py' first.")
            sys.exit(1)

        with open(meta_file, "r", encoding="utf-8") as f:
            stats = json.load(f)
        print("=== INDEX STATISTICS ===")
        print(f"Total Chunks        : {stats.get('chunk_count')}")
        print(f"Embedding Model     : {stats.get('model_name')}")
        print(f"Vector Dimensions   : {stats.get('embedding_dimension')}")
        print(f"Indexed Documents   :")
        for doc in stats.get("doc_names", []):
            print(f"  - {doc}")
        sys.exit(0)

    # Build index
    if not args.force and searcher.is_index_valid():
        print("Index is already up to date. Use --force to rebuild.")
        sys.exit(0)

    print("Starting document ingestion and index construction...")
    pages = ingest_documents()
    if not pages:
        print("ERROR: No document pages could be extracted.")
        sys.exit(1)

    chunks = chunk_all_pages(pages)
    print(f"Created {len(chunks)} chunks across {len(pages)} pages.")

    searcher.build_index(chunks, force=args.force)
    print("SUCCESS: Hybrid index built and saved successfully.")


if __name__ == "__main__":
    main()


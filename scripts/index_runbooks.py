import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from healer.src.rag.runbook_indexer import indexer


def main():
    parser = argparse.ArgumentParser(description="Index and query healer runbooks.")
    parser.add_argument("--query", default="", help="Optional query to test retrieval.")
    parser.add_argument("--force", action="store_true", help="Force reindex even when hashes match.")
    parser.add_argument("--limit", type=int, default=3, help="Number of matches to show.")
    args = parser.parse_args()

    indexer.index_runbooks(force=args.force)

    if args.query:
        matches = indexer.search(args.query, limit=args.limit)
        print(json.dumps(matches, indent=2))


if __name__ == "__main__":
    main()

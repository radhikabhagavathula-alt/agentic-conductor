"""One-off migration + calibration helper for the ChromaDB fact-check store.

    python ingest_memory.py
    python ingest_memory.py --query "how long did the Taj Mahal take to build"

--query prints the raw cosine distance and tier of the nearest entries. Use it to tune
FACTCHECK_MATCH_DISTANCE / FACTCHECK_RELATED_DISTANCE for your embedding model.
"""

import argparse
import json
import os

import vector_store

LEGACY_FILE = "memory_store.json"


def migrate(path: str = LEGACY_FILE) -> int:
    if not os.path.exists(path):
        print(f"{path} not found - nothing to migrate.")
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    n = 0
    for topic, entry in data.get("claims", {}).items():
        vector_store.upsert_fact_check(
            topic=topic,
            claim=entry["claim"],
            verdict=entry["verdict"],
            sources=entry["sources"],  # parse_sources() strips the stray leading spaces
            timestamp=entry.get(
                "timestamp"
            ),  # keep original date so staleness stays honest
        )
        n += 1
    print(
        f"Migrated {n} fact-check(s) into {vector_store._state['path'] or vector_store._default_path()}."
    )
    return n


def query(text: str) -> None:
    hits = vector_store.search(text, k=5)
    if not hits:
        print("No results within the RELATED distance threshold.")
    for h in hits:
        print(
            f"[{h.tier:7}] distance={h.distance:<6} age={h.age_days}d  topic={h.topic!r}"
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", help="search instead of migrating")
    ap.add_argument(
        "--legacy", default=LEGACY_FILE, help="path to old memory_store.json"
    )
    args = ap.parse_args()
    query(args.query) if args.query else migrate(args.legacy)

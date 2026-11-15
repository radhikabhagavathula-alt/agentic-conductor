"""ChromaDB-backed semantic store for completed fact-checks (the RAG layer).

Replaces the exact-match JSON lookup in the old memory_tools.py:

    old:  "Taj Mahal" == "taj mahal"            -> hit,  "Taj Mahal history" -> miss
    new:  nearest-neighbour search over embeddings -> both are hits

Design notes
------------
* We compute embeddings ourselves (``embed``) and hand vectors to Chroma. That keeps
  one seam for swapping the embedding model (local MiniLM today, Bedrock/Voyage/OpenAI
  tomorrow) and lets tests inject a deterministic fake so CI never downloads a model.
* Distances are cosine distances (0 = identical direction, higher = less similar).
* A fact-check cache must be conservative: a *near* topic is not the *same* claim.
  So retrieval returns a tiered result - MATCH (safe to reuse), RELATED (context only),
  or nothing - and anything older than MAX_AGE_DAYS is never a MATCH (facts go stale).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

import chromadb

COLLECTION_NAME = "fact_checks"

# Starting points, NOT universal constants - calibrate with `scripts/ingest_memory.py --query`.
MATCH_MAX_DISTANCE = float(os.environ.get("FACTCHECK_MATCH_DISTANCE", "0.35"))
RELATED_MAX_DISTANCE = float(os.environ.get("FACTCHECK_RELATED_DISTANCE", "0.60"))
MAX_AGE_DAYS = int(os.environ.get("FACTCHECK_MAX_AGE_DAYS", "90"))
TOP_K = int(os.environ.get("FACTCHECK_TOP_K", "3"))

Embedder = Callable[[Sequence[str]], "list[list[float]]"]

_state: dict = {"path": None, "embedder": None, "collection": None}


# ----------------------------------------------------------------------------
# Configuration / lazy singletons
# ----------------------------------------------------------------------------

def _default_path() -> str:
    return os.environ.get("FACTCHECK_CHROMA_PATH", "chroma_db")


def _default_embedder() -> Embedder:
    # Imported lazily: the ONNX MiniLM model is only downloaded/loaded on first real use.
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    ef = DefaultEmbeddingFunction()
    return lambda texts: [list(map(float, v)) for v in ef(list(texts))]


def configure(path: Optional[str] = None, embedder: Optional[Embedder] = None) -> None:
    """(Re)configure the store. Tests call this to use a temp dir and a fake embedder."""
    _state["path"] = path
    _state["embedder"] = embedder
    _state["collection"] = None


def embed(texts: Sequence[str]) -> "list[list[float]]":
    if _state["embedder"] is None:
        _state["embedder"] = _default_embedder()
    return _state["embedder"](texts)


def get_collection():
    if _state["collection"] is None:
        client = chromadb.PersistentClient(path=_state["path"] or _default_path())
        _state["collection"] = client.get_or_create_collection(
            name=COLLECTION_NAME,
            configuration={"hnsw": {"space": "cosine"}},
        )
    return _state["collection"]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def parse_sources(raw) -> "list[str]":
    """Accept 'a, b,c' or a list; strip whitespace (the old JSON store kept leading spaces)."""
    items = raw.split(",") if isinstance(raw, str) else list(raw or [])
    return [s.strip() for s in items if s and s.strip()]


def _views(topic: str, claim: str) -> "dict[str, str]":
    """Two text views of one fact-check, each embedded separately.

    A short query like "Taj Mahal" is far from a long "topic + claim" vector (the claim
    dilutes it), while a specific question matches the claim better than the bare topic.
    Indexing both and taking the best distance handles either kind of query.
    """
    return {"topic": topic.strip(), "claim": f"{topic.strip()}: {claim.strip()}"}


def _doc_id(topic: str, claim: str) -> str:
    norm = f"{topic.strip().lower()}||{' '.join(claim.lower().split())}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


@dataclass
class Hit:
    topic: str
    claim: str
    verdict: str
    sources: "list[str]"
    timestamp: str
    distance: float
    age_days: int
    tier: str  # "MATCH" | "RELATED"


def _age_days(iso_ts: str, now: datetime) -> int:
    return max(0, (now - datetime.fromisoformat(iso_ts)).days)


# ----------------------------------------------------------------------------
# Write path
# ----------------------------------------------------------------------------

def upsert_fact_check(
    topic: str,
    claim: str,
    verdict: str,
    sources,
    timestamp: Optional[str] = None,
) -> str:
    """Insert or refresh a fact-check. Same topic+claim -> same id -> overwritten, not duplicated."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    parent_id = _doc_id(topic, claim)
    views = _views(topic, claim)
    base_meta = {
        "parent_id": parent_id,
        "topic": topic.strip(),
        "claim": claim.strip(),
        "verdict": verdict.strip(),
        "sources_json": json.dumps(parse_sources(sources)),  # Chroma metadata must be scalar
        "timestamp": ts,
    }
    get_collection().upsert(
        ids=[f"{parent_id}:{kind}" for kind in views],
        documents=list(views.values()),
        embeddings=embed(list(views.values())),
        metadatas=[{**base_meta, "kind": kind} for kind in views],
    )
    return parent_id


def entry_count() -> int:
    """Number of distinct fact-checks (each is indexed as two records)."""
    return len(get_collection().get(where={"kind": "topic"}, include=[])["ids"])


# ----------------------------------------------------------------------------
# Read path
# ----------------------------------------------------------------------------

def search(query: str, k: int = TOP_K, now: Optional[datetime] = None) -> "list[Hit]":
    """Semantic search. Returns up to k distinct fact-checks within RELATED_MAX_DISTANCE, closest first."""
    col = get_collection()
    total = col.count()
    if total == 0 or not query.strip():
        return []

    now = now or datetime.now(timezone.utc)
    res = col.query(
        query_embeddings=embed([query.strip()]),
        n_results=min(k * 2, total),  # two records per fact-check -> over-fetch, then de-duplicate
        include=["metadatas", "distances"],
    )

    best: "dict[str, tuple[float, dict]]" = {}
    for meta, dist in zip(res["metadatas"][0], res["distances"][0]):
        pid = meta["parent_id"]
        if pid not in best or dist < best[pid][0]:
            best[pid] = (float(dist), meta)

    hits: "list[Hit]" = []
    for dist, meta in sorted(best.values(), key=lambda x: x[0]):
        if dist > RELATED_MAX_DISTANCE:
            continue
        age = _age_days(meta["timestamp"], now)
        fresh_and_close = dist <= MATCH_MAX_DISTANCE and age <= MAX_AGE_DAYS
        hits.append(
            Hit(
                topic=meta["topic"],
                claim=meta["claim"],
                verdict=meta["verdict"],
                sources=json.loads(meta["sources_json"]),
                timestamp=meta["timestamp"],
                distance=round(dist, 3),
                age_days=age,
                tier="MATCH" if fresh_and_close else "RELATED",
            )
        )
    return hits[:k]

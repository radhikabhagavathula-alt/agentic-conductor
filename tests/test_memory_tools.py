"""Tests for the ChromaDB-backed memory tools.

A deterministic bag-of-words embedder replaces the real model, so these tests are fast,
offline, and need no model download in CI. They verify the retrieval *logic* (tiers,
staleness, dedupe, persistence) - not the quality of a real embedding model.
"""

from datetime import datetime, timedelta, timezone

import pytest

import memory_tools
import vector_store
from fake_embedder import fake_embedder


@pytest.fixture(autouse=True)
def isolated_store(tmp_path):
    """Fresh Chroma dir + fake embedder per test; the real chroma_db/ is never touched."""
    vector_store.configure(path=str(tmp_path / "chroma"), embedder=fake_embedder)
    yield tmp_path
    vector_store.configure()  # reset singletons


def _text(result):
    return result["content"][0]["text"]


async def _save(topic="Taj Mahal", claim="The Taj Mahal mausoleum took 17 years to build.",
                verdict="TRUE", sources="https://a.com, https://b.com"):
    return await memory_tools.save_to_memory(
        {"topic": topic, "claim": claim, "verdict": verdict, "sources": sources}
    )


@pytest.mark.asyncio
async def test_empty_store_returns_not_found():
    text = _text(await memory_tools.check_memory({"topic": "anything"}))
    assert "Not found" in text


@pytest.mark.asyncio
async def test_save_then_check_round_trip_is_case_insensitive():
    await _save()
    text = _text(await memory_tools.check_memory({"topic": "taj mahal"}))
    assert text.startswith("FOUND")
    assert "17 years" in text
    assert "TRUE" in text


@pytest.mark.asyncio
async def test_semantic_query_matches_rephrased_topic():
    """The point of RAG: a reworded query still hits (exact-match JSON would miss)."""
    await _save()
    text = _text(await memory_tools.check_memory({"topic": "How many years did the Taj Mahal take to build"}))
    assert text.startswith("FOUND")


@pytest.mark.asyncio
async def test_short_topic_query_is_not_diluted_by_a_long_claim():
    """Regression: a bare topic must stay close to its entry even when the claim is long."""
    long_claim = " ".join(["The monument was commissioned in 1631 and finished in 1648."] * 6)
    await _save(claim=long_claim)
    hit = vector_store.search("Taj Mahal")[0]
    assert hit.tier == "MATCH"
    assert hit.distance < vector_store.MATCH_MAX_DISTANCE


@pytest.mark.asyncio
async def test_unrelated_topic_is_not_a_match():
    await _save()
    text = _text(await memory_tools.check_memory({"topic": "Quantum entanglement in photosynthesis"}))
    assert "FOUND" not in text


@pytest.mark.asyncio
async def test_resaving_same_claim_upserts_instead_of_duplicating():
    await _save(verdict="TRUE")
    await _save(verdict="PARTIALLY TRUE")
    assert vector_store.entry_count() == 1
    assert "PARTIALLY TRUE" in _text(await memory_tools.check_memory({"topic": "Taj Mahal"}))


@pytest.mark.asyncio
async def test_sources_are_stripped_and_split():
    await _save(sources=" https://a.com ,https://b.com,, ")
    hit = vector_store.search("Taj Mahal")[0]
    assert hit.sources == ["https://a.com", "https://b.com"]


@pytest.mark.asyncio
async def test_stale_entry_is_never_a_confident_match():
    old = (datetime.now(timezone.utc) - timedelta(days=vector_store.MAX_AGE_DAYS + 30)).isoformat()
    vector_store.upsert_fact_check(
        "Taj Mahal", "The Taj Mahal mausoleum took 17 years to build.", "TRUE", "https://a.com", timestamp=old
    )
    text = _text(await memory_tools.check_memory({"topic": "Taj Mahal"}))
    assert text.startswith("NO CONFIDENT MATCH")
    assert "FOUND" not in text.split("\n")[0]


@pytest.mark.asyncio
async def test_distance_thresholds_control_tiers(monkeypatch):
    await _save()
    monkeypatch.setattr(vector_store, "MATCH_MAX_DISTANCE", -1.0)  # nothing is "close enough" to reuse
    text = _text(await memory_tools.check_memory({"topic": "Taj Mahal"}))
    assert text.startswith("NO CONFIDENT MATCH")


def test_data_persists_across_client_restart(isolated_store):
    vector_store.upsert_fact_check("Persist", "A claim about persistence.", "TRUE", "https://x.com")
    vector_store.configure(path=str(isolated_store / "chroma"), embedder=fake_embedder)  # simulate restart
    assert vector_store.entry_count() == 1
    assert vector_store.search("Persist")[0].topic == "Persist"

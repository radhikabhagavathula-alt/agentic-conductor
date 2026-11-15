import json

import pytest

import ingest_memory
import vector_store
from fake_embedder import fake_embedder


@pytest.fixture(autouse=True)
def isolated_store(tmp_path):
    vector_store.configure(path=str(tmp_path / "chroma"), embedder=fake_embedder)
    yield
    vector_store.configure()


def test_migrate_imports_legacy_json_and_cleans_sources(tmp_path):
    legacy = tmp_path / "memory_store.json"
    legacy.write_text(json.dumps({
        "claims": {
            "taj mahal": {
                "claim": "Built over 17 years.",
                "verdict": "TRUE",
                "sources": ["https://a.com", " https://b.com"],  # leading space like the real file
                "timestamp": "2026-07-17T11:12:34+00:00",
            }
        },
        "session_log": [],
    }), encoding="utf-8")

    assert ingest_memory.migrate(str(legacy)) == 1
    hit = vector_store.search("taj mahal")[0]
    assert hit.sources == ["https://a.com", "https://b.com"]
    assert hit.timestamp.startswith("2026-07-17")  # original date preserved


def test_migrate_missing_file_is_a_noop(tmp_path):
    assert ingest_memory.migrate(str(tmp_path / "nope.json")) == 0

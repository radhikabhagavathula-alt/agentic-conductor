import json
import pytest
import memory_tools

@pytest.fixture(autouse=True)
def isolated_memory_file(tmp_path, monkeypatch):
    """Redirect MEMORY_FILE to a temp path so tests never touch the real memory store."""
    test_file = tmp_path / "test_memory_store.json"
    monkeypatch.setattr(memory_tools, "MEMORY_FILE", str(test_file))
    yield test_file

@pytest.mark.asyncio
async def test_check_memory_returns_not_found_when_empty():
    result = await memory_tools.check_memory({"topic": "unknown topic"})
    text = result["content"][0]["text"]
    assert "Not found" in text

@pytest.mark.asyncio
async def test_save_then_check_memory_round_trip():
    await memory_tools.save_to_memory({
        "topic": "Test Topic",
        "claim": "Test claim text",
        "verdict": "TRUE",
        "sources": "https://example.com,https://example2.com",
    })

    result = await memory_tools.check_memory({"topic": "test topic"})  # different case
    text = result["content"][0]["text"]

    assert "FOUND" in text
    assert "Test claim text" in text
    assert "TRUE" in text

def test_memory_file_written_as_valid_json(isolated_memory_file):
    import asyncio
    asyncio.run(memory_tools.save_to_memory({
        "topic": "JSON check",
        "claim": "c",
        "verdict": "TRUE",
        "sources": "https://example.com",
    }))

    with open(isolated_memory_file, "r", encoding="utf-8") as f:
        data = json.load(f)  # raises if malformed

    assert "json check" in data["claims"]
    assert len(data["session_log"]) == 1
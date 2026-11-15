import json
from datetime import datetime

import pytest

from hooks import block_lead_websearch, log_tool_use, safety_hooks


def test_safety_hooks_register_policy_and_audit_callbacks():
    pre_tool_use = safety_hooks["PreToolUse"][0]
    post_tool_use = safety_hooks["PostToolUse"][0]

    assert pre_tool_use.matcher == "WebSearch"
    assert pre_tool_use.hooks == [block_lead_websearch]
    assert post_tool_use.matcher is None
    assert post_tool_use.hooks == [log_tool_use]


@pytest.mark.asyncio
async def test_lead_direct_websearch_is_blocked():
    """The lead agent (no agent_id) calling WebSearch directly must be denied."""
    input_data = {"tool_name": "WebSearch", "tool_input": {"query": "test"}}
    result = await block_lead_websearch(input_data, "tool_use_1", {})

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "delegate" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()
    )


@pytest.mark.asyncio
async def test_subagent_websearch_is_allowed():
    """A subagent (agent_id present) calling WebSearch must NOT be denied."""
    input_data = {
        "tool_name": "WebSearch",
        "tool_input": {"query": "test"},
        "agent_id": "abc123",
        "agent_type": "researcher",
    }
    result = await block_lead_websearch(input_data, "tool_use_2", {})

    assert result == {}


@pytest.mark.asyncio
async def test_non_websearch_tool_is_ignored():
    """The hook should only ever act on WebSearch calls, never other tools."""
    input_data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    result = await block_lead_websearch(input_data, "tool_use_3", {})

    assert result == {}


@pytest.mark.asyncio
async def test_log_tool_use_appends_structured_jsonl_record(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_data = {
        "tool_name": "WebSearch",
        "tool_input": {"query": "test"},
        "parent_tool_use_id": "parent_1",
    }

    result = await log_tool_use(input_data, "tool_use_4", {})

    assert result == {}
    entry = json.loads((tmp_path / "tool_log.jsonl").read_text(encoding="utf-8"))
    assert entry["tool_name"] == "WebSearch"
    assert entry["tool_input"] == {"query": "test"}
    assert entry["parent_tool_use_id"] == "parent_1"
    datetime.fromisoformat(entry["timestamp"])

import pytest
from hooks import block_lead_websearch

@pytest.mark.asyncio
async def test_lead_direct_websearch_is_blocked():
    """The lead agent (no agent_id) calling WebSearch directly must be denied."""
    input_data = {"tool_name": "WebSearch", "tool_input": {"query": "test"}}
    result = await block_lead_websearch(input_data, "tool_use_1", {})

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "delegate" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

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
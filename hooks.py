import json
from datetime import datetime, timezone
from claude_agent_sdk import HookMatcher

async def block_lead_websearch(input_data, tool_use_id, context):
    tool_name = input_data.get("tool_name")
    is_subagent_call = "agent_id" in input_data

    if tool_name == "WebSearch" and not is_subagent_call:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Lead agent must delegate search to a subagent, not search directly.",
            }
        }
    return {}

async def log_tool_use(input_data, tool_use_id, context):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": input_data.get("tool_name"),
        "tool_input": input_data.get("tool_input"),
        "parent_tool_use_id": input_data.get("parent_tool_use_id"),
    }
    with open("tool_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {}

safety_hooks = {
    "PreToolUse": [HookMatcher(matcher="WebSearch", hooks=[block_lead_websearch])],
    "PostToolUse": [HookMatcher(matcher=None, hooks=[log_tool_use])],
}
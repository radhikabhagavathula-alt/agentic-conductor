import json
import os
from datetime import datetime, timezone
from claude_agent_sdk import tool, create_sdk_mcp_server

MEMORY_FILE = "memory_store.json"


def _load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"claims": {}, "session_log": []}

    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -------------------------------------------------------------------
# Plain Python functions (used by tests)
# -------------------------------------------------------------------

async def check_memory(args):
    data = _load_memory()
    topic_key = args["topic"].strip().lower()

    if topic_key in data["claims"]:
        entry = data["claims"][topic_key]
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"FOUND prior fact-check from {entry['timestamp']}:\n"
                        f"Claim: {entry['claim']}\n"
                        f"Verdict: {entry['verdict']}\n"
                        f"Sources: {', '.join(entry['sources'])}"
                    ),
                }
            ]
        }

    return {
        "content": [
            {
                "type": "text",
                "text": "Not found in memory. This topic has not been fact-checked before.",
            }
        ]
    }


async def save_to_memory(args):
    data = _load_memory()

    topic_key = args["topic"].strip().lower()

    data["claims"][topic_key] = {
        "claim": args["claim"],
        "verdict": args["verdict"],
        "sources": args["sources"].split(","),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    data["session_log"].append(
        {
            "topic": args["topic"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    _save_memory(data)

    return {
        "content": [
            {
                "type": "text",
                "text": f"Saved fact-check for '{args['topic']}' to memory.",
            }
        ]
    }


# -------------------------------------------------------------------
# Claude SDK tool wrappers
# -------------------------------------------------------------------

check_memory_tool = tool(
    "check_memory",
    "Check if a topic has already been fact-checked before, to avoid redundant research.",
    {"topic": str},
)(check_memory)

save_to_memory_tool = tool(
    "save_to_memory",
    "Save a completed fact-check to memory for future reuse.",
    {
        "topic": str,
        "claim": str,
        "verdict": str,
        "sources": str,
    },
)(save_to_memory)


# -------------------------------------------------------------------
# MCP Server
# -------------------------------------------------------------------

memory_server = create_sdk_mcp_server(
    name="memory-tools",
    version="1.0.0",
    tools=[
        check_memory_tool,
        save_to_memory_tool,
    ],
)
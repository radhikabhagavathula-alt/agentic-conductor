import anyio
from claude_agent_sdk import tool, create_sdk_mcp_server

import vector_store


def _text(msg: str) -> dict:
    return {"content": [{"type": "text", "text": msg}]}


def _fmt(hit: "vector_store.Hit") -> str:
    return (
        f"- Topic: {hit.topic}\n"
        f"  Claim: {hit.claim}\n"
        f"  Verdict: {hit.verdict}\n"
        f"  Sources: {', '.join(hit.sources)}\n"
        f"  (checked {hit.timestamp[:10]}, {hit.age_days}d ago; distance {hit.distance})"
    )


# -------------------------------------------------------------------
# Plain async functions (used by tests)
# -------------------------------------------------------------------


async def check_memory(args):
    query = args["topic"]
    # Chroma + the embedder are synchronous/CPU-bound: keep them off the event loop.
    hits = await anyio.to_thread.run_sync(vector_store.search, query)

    matches = [h for h in hits if h.tier == "MATCH"]
    related = [h for h in hits if h.tier == "RELATED"]

    if matches:
        best, others = matches[0], matches[1:] + related
        out = ["FOUND prior fact-check (semantic match):", _fmt(best)]
        if others:
            out += ["", "Other related prior fact-checks (context only):"] + [
                _fmt(h) for h in others
            ]
        return _text("\n".join(out))

    if related:
        return _text(
            "NO CONFIDENT MATCH. Related prior fact-checks exist but are too distant or too old "
            f"(> {vector_store.MAX_AGE_DAYS} days) to reuse as the answer. Treat as not found and "
            "research the topic; use these only as context:\n"
            + "\n".join(_fmt(h) for h in related)
        )

    return _text("Not found in memory. This topic has not been fact-checked before.")


async def save_to_memory(args):
    await anyio.to_thread.run_sync(
        lambda: vector_store.upsert_fact_check(
            topic=args["topic"],
            claim=args["claim"],
            verdict=args["verdict"],
            sources=args["sources"],
        )
    )
    return _text(f"Saved fact-check for '{args['topic']}' to memory.")


# -------------------------------------------------------------------
# Claude SDK tool wrappers
# -------------------------------------------------------------------

check_memory_tool = tool(
    "check_memory",
    "Semantic search over prior fact-checks. Returns FOUND (reuse it), NO CONFIDENT MATCH "
    "(research instead), or Not found. Use before doing any new research.",
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
    version="2.0.0",
    tools=[
        check_memory_tool,
        save_to_memory_tool,
    ],
)

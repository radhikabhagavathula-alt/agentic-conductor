import anyio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, AgentDefinition
from hooks import safety_hooks
from memory_tools import memory_server

researcher = AgentDefinition(
    description="Finds a specific factual claim on a topic using web search. Reports the claim plainly with no analysis.",
    prompt="You are a researcher. Given a topic, find ONE specific, checkable factual claim about it using WebSearch. Report just the claim in one or two sentences — no commentary.",
    tools=["WebSearch"],
    model="claude-sonnet-4-6",
)

fact_checker = AgentDefinition(
    description="Independently verifies a factual claim using web search and reports a confidence level with sources.",
    prompt="You are a fact-checker. Given a claim, independently search the web to verify it. State whether it is TRUE, FALSE, or UNCERTAIN, with a one-line reason and your source.",
    tools=["WebSearch"],
    model="claude-sonnet-4-6",
)


async def main():
    options = ClaudeAgentOptions(
        system_prompt=(
            "You coordinate a fact-checking pipeline with semantic memory (RAG over past fact-checks). "
            "FIRST, always call check_memory with the topic. It searches prior fact-checks by meaning, "
            "so a differently worded topic can still match. "
            "If the result starts with 'FOUND', report that cached fact-check directly - do NOT re-research. "
            "If it says 'NO CONFIDENT MATCH' or 'Not found', treat the topic as new; related entries "
            "listed under NO CONFIDENT MATCH are context only and must never be reported as the verdict. "
            "For a new topic: delegate to the researcher subagent to find one claim, "
            "then delegate that claim to the fact-checker subagent to verify it, "
            "then call save_to_memory with the topic, claim, verdict, and comma-separated sources. "
            "Finally, summarize the result for the user."
        ),
        model="claude-sonnet-4-6",
        agents={"researcher": researcher, "fact-checker": fact_checker},
        tools=[
            "Agent",
            "WebSearch",
            "mcp__memory-tools__check_memory",
            "mcp__memory-tools__save_to_memory",
        ],
        allowed_tools=[
            "Agent",
            "WebSearch",
            "mcp__memory-tools__check_memory",
            "mcp__memory-tools__save_to_memory",
        ],
        disallowed_tools=["Bash", "Write", "Edit", "WebFetch"],
        permission_mode="dontAsk",
        mcp_servers={"memory-tools": memory_server},
        hooks=safety_hooks,
        setting_sources=["project"],
        max_turns=8,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Topic: Taj Mahal")
        async for message in client.receive_response():
            print(message)


if __name__ == "__main__":
    anyio.run(main)

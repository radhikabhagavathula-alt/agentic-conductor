import anyio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from mcp_tools import research_tools_server

async def main():
    options = ClaudeAgentOptions(
        system_prompt="You are a research assistant. When you learn a useful fact, save it using save_finding.",
        model="claude-sonnet-4-6",
        tools=["WebSearch", "mcp__research-tools__save_finding"],
        allowed_tools=["WebSearch", "mcp__research-tools__save_finding"],
        disallowed_tools=["Bash", "Write", "Edit", "WebFetch"],
        permission_mode="dontAsk",
        mcp_servers={"research-tools": research_tools_server},
        max_turns=5,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Find out what year the Eiffel Tower was completed, and save that fact as a finding.")
        async for message in client.receive_response():
            print(message)

anyio.run(main)
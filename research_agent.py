import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    options = ClaudeAgentOptions(
        system_prompt="You are a concise research assistant. Answer factually and briefly.",
        model="claude-sonnet-4-6",
        tools=["WebSearch"],           # <- restricts what's even loaded into context
        allowed_tools=["WebSearch"],   # <- auto-approves it, no permission prompt
        disallowed_tools=["Bash", "Write", "Edit", "WebFetch"],  # <- hard block, belt & suspenders
        permission_mode="dontAsk",     # <- anything not explicitly approved is denied, not prompted
        max_turns=3,
    )

    async for message in query(prompt="What year was the Eiffel Tower completed?", options=options):
        print(message)

anyio.run(main)
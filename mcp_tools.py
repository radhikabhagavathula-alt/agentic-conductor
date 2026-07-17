from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("save_finding", "Save a research finding to findings.md for later reference", {"finding": str})
async def save_finding(args):
    with open("findings.md", "a", encoding="utf-8") as f:
        f.write(f"- {args['finding']}\n")
    return {
        "content": [
            {"type": "text", "text": f"Saved finding: {args['finding']}"}
        ]
    }

research_tools_server = create_sdk_mcp_server(
    name="research-tools",
    version="1.0.0",
    tools=[save_finding],
)
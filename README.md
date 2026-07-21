# Agentic Conductor

A hands-on portfolio of **AI agent orchestration patterns** built on the Claude Agent SDK — covering tool restriction, custom MCP tool servers, safety hooks, multi-agent delegation, and persistent memory. The project demonstrates production-relevant patterns for building controllable, auditable, and reusable AI agents, rather than a single end-to-end application.

## What This Project Demonstrates

| Capability | Where It's Implemented |
|---|---|
| **Tool-scoped agents** — restricting a single agent to only the tools it needs, with hard-denied tools as a safety net | `research_agent.py` |
| **Custom MCP tool servers** — exposing a bespoke Python function (`save_finding`) as a callable tool via the Claude Agent SDK | `mcp_tools.py`, `custom_tools_agent.py` |
| **Lifecycle hooks** — intercepting tool calls before/after execution to enforce policy (e.g., blocking the lead agent from searching directly) and to log every tool invocation for auditability | `hooks.py` |
| **Multi-agent orchestration** — a lead agent coordinating a two-stage `researcher → fact-checker` pipeline, each subagent scoped to its own prompt, tools, and model | `subagent_team.py` |
| **Persistent memory** — a JSON-backed memory store so the agent team checks for previously fact-checked claims before re-researching, avoiding redundant work | `memory_tools.py` |
| **Automated testing & CI** | `tests/`, `.github/workflows/`, `hook_test.py`, `sanity_check.py` |

## Architecture at a Glance
subagent_team.py            (lead agent / conductor)
├── researcher             → finds one checkable claim (WebSearch only)
├── fact-checker           → independently verifies the claim (WebSearch only)
├── memory-tools (MCP)     → check_memory / save_to_memory (JSON store)
└── safety_hooks           → PreToolUse (deny direct lead search)
PostToolUse (log every tool call to tool_log.jsonl)

The lead agent never searches the web itself — a `PreToolUse` hook enforces delegation to subagents, and every tool call across the whole run is logged for traceability. Before spinning up a new research/verification cycle, the system checks memory for an existing verdict on the same topic and reuses it if found.

## Key Engineering Practices Highlighted

- **Least-privilege tool access:** every agent explicitly whitelists (`allowed_tools`) and blacklists (`disallowed_tools`) its capabilities, with `permission_mode="dontAsk"` meaning anything unlisted is denied by default rather than silently allowed.
- **Separation of concerns:** research (fact-finding) and verification (fact-checking) are handled by independent subagents with distinct prompts and models, avoiding a single agent grading its own work.
- **Observability:** a `PostToolUse` hook persists a structured, timestamped log (`tool_log.jsonl`) of every tool call made across the agent hierarchy, including parent/child agent relationships.
- **Statefulness without a database:** a lightweight JSON memory store lets the pipeline skip redundant fact-checks, demonstrating a simple pattern for agent memory that can be swapped for a real database later.
- **Test coverage:** dedicated test files validate hook behavior (`hook_test.py`) and overall pipeline sanity (`sanity_check.py`), backed by a GitHub Actions workflow for CI.

## Tech Stack

- **Language:** Python
- **Core SDK:** Claude Agent SDK (`claude_agent_sdk`) — `ClaudeAgentOptions`, `ClaudeSDKClient`, `AgentDefinition`, `HookMatcher`, MCP tool servers
- **Async runtime:** `anyio`
- **CI/CD:** GitHub Actions

## Repository Structure
.
├── custom_tools_agent.py     # Single agent using a custom MCP tool (save_finding)
├── research_agent.py         # Minimal, tool-restricted research agent
├── subagent_team.py          # Multi-agent fact-checking pipeline with memory + hooks
├── mcp_tools.py               # Custom MCP tool server definition
├── memory_tools.py            # JSON-backed memory MCP tool server
├── hooks.py                   # PreToolUse / PostToolUse safety and logging hooks
├── hook_test.py                # Hook behavior tests
├── sanity_check.py             # Pipeline sanity tests
├── tests/                      # Test suite
├── .github/workflows/          # CI configuration
└── requirements-dev.txt        # Development dependencies

## Project Milestones

1. **Single tool-restricted agent** — a minimal agent limited to `WebSearch`, with all other tools explicitly denied (`research_agent.py`).
2. **Custom MCP tool integration** — exposing a hand-written Python function as an agent-callable tool via a custom MCP server (`mcp_tools.py`, `custom_tools_agent.py`).
3. **Persistent memory layer** — a JSON-backed store (`memory_tools.py`) letting an agent check for and save prior results instead of repeating work.
4. **Safety and observability hooks** — `PreToolUse`/`PostToolUse` hooks that enforce delegation policy and log every tool call (`hooks.py`).
5. **Multi-agent delegation** — a lead agent coordinating specialized `researcher` and `fact-checker` subagents (`subagent_team.py`).
6. **End-to-end pipeline integration** — wiring memory, hooks, and subagents together into a single fact-checking workflow with defined turn limits and tool permissions.
7. **Automated test coverage** — unit tests validating hook behavior and pipeline sanity (`hook_test.py`, `sanity_check.py`, `tests/`).
8. **Skills** — the project as a whole demonstrates applied skills in: agentic system design (permissioning, delegation, orchestration), the Claude Agent SDK API surface (`ClaudeAgentOptions`, `ClaudeSDKClient`, `AgentDefinition`, `HookMatcher`), MCP server/tool authoring, async Python (`anyio`), lightweight state management without a database, and test-driven validation of agent behavior backed by CI (GitHub Actions).

## Why It Matters

This project is a compact reference for the patterns needed to move AI agents from "demo" to "trustworthy system": scoped permissions, enforced delegation, audit logging, and stateful memory — the building blocks recruiters and engineering teams look for when evaluating experience with real-world agentic AI development.

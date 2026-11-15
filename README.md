# Agentic Conductor

Agentic Conductor is a small fact-checking workflow and a portfolio of AI agent orchestration patterns.

## Problem Statement

Fact-checking a topic involves finding a specific factual claim, verifying it against web sources, and making the evidence behind the result easy to review. Repeating this work can waste research time and make previous findings difficult to reuse. This project demonstrates a workflow that delegates claim discovery and independent verification to separate agents, reuses prior fact-checks through semantic retrieval (RAG over ChromaDB), and logs tool activity. It helps users produce a concise, evidence-backed result with a traceable process, while leaving the final assessment to human review.

## What This Project Demonstrates

| Capability | Where It's Implemented |
|---|---|
| **Tool-scoped subagents** — limiting the researcher and fact-checker to WebSearch, with other tools explicitly denied | `fact_check_pipeline.py` |
| **Lifecycle hooks** — intercepting tool calls before/after execution to enforce policy (e.g., blocking the lead agent from searching directly) and to log every tool invocation for auditability | `hooks.py` |
| **Multi-agent orchestration** — a lead agent coordinating a two-stage `researcher → fact-checker` pipeline, each subagent scoped to its own prompt, tools, and model | `fact_check_pipeline.py` |
| **RAG memory over ChromaDB** — semantic search over prior fact-checks with distance thresholds and a freshness window; saves new results as embeddings to avoid repeated research | `memory_tools.py`, `vector_store.py`, `chroma_db/` |
| **Automated testing & CI** | `tests/`, `.github/workflows/` |

## Architecture and Component Roles

<table>
	<thead>
		<tr><th colspan="3">Main fact-checking flow</th></tr>
	</thead>
	<tbody>
		<tr>
			<td colspan="3" align="center"><strong>1. Trigger the lead agent</strong><br>Run <code>python fact_check_pipeline.py</code> → <code>anyio.run(main)</code> starts the client → <code>client.query("Topic: Taj Mahal")</code> sends the current hard-coded topic</td>
		</tr>
		<tr>
			<td colspan="3" align="center"><strong>2. Lead agent coordinates</strong><br><code>fact_check_pipeline.py</code> runs the fact-checking workflow</td>
		</tr>
		<tr>
			<td colspan="3" align="center"><strong>3. Check memory</strong><br><code>memory_tools.py</code> runs a semantic search over prior fact-checks in ChromaDB (<code>vector_store.py</code>)</td>
		</tr>
		<tr>
			<td align="center"><strong>Found</strong><br>a close, fresh match is returned (stale or distant matches are treated as not found)</td>
			<td align="center"><strong>OR</strong></td>
			<td align="center"><strong>Not found</strong><br>↓<br>Researcher agent in <code>fact_check_pipeline.py</code> finds a checkable claim with WebSearch<br>↓<br>Fact-checker agent in <code>fact_check_pipeline.py</code> independently verifies it<br>↓<br><code>memory_tools.py</code> embeds and saves the claim, verdict, and sources to ChromaDB</td>
		</tr>
		<tr>
			<td colspan="3" align="center"><strong>4. Report either path</strong><br>↓<br><code>.claude/skills/fact-check-report/SKILL.md</code> describes the report format → evidence-backed result for human review</td>
		</tr>
		<tr>
			<td colspan="3"><strong>Throughout the run:</strong> <code>hooks.py</code> blocks direct WebSearch by the lead agent and records tool calls in <code>tool_log.jsonl</code>.</td>
		</tr>
	</tbody>
</table>

<table>
	<thead>
		<tr><th>Supporting component</th><th>Why it matters</th></tr>
	</thead>
	<tbody>
		<tr><td><code>tests/test_hooks.py</code></td><td>Unit-tests that lead-agent searches are blocked while subagent searches are allowed.</td></tr>
		<tr><td><code>tests/test_memory_tools.py</code></td><td>Tests semantic lookup, match/related/stale tiers, upsert de-duplication, and persistence using an isolated temporary Chroma directory and a deterministic offline embedder.</td></tr>
		<tr><td><code>tests/test_ingest_memory.py</code></td><td>Tests migration of the legacy <code>memory_store.json</code> into ChromaDB.</td></tr>
		<tr><td><code>.github/workflows/tests.yml</code> + <code>requirements-dev.txt</code></td><td>Install test dependencies and run the test suite in GitHub Actions.</td></tr>
	</tbody>
</table>

## Run Tests

From the project root, run the complete test suite with:

```powershell
python -m pytest tests/ -v
```

Pytest discovers and runs every `test_*.py` file under `tests/`; the unit tests remain independently testable.

## Key Engineering Practices Highlighted

- **Least-privilege tool access:** every agent explicitly whitelists (`allowed_tools`) and blacklists (`disallowed_tools`) its capabilities, with `permission_mode="dontAsk"` meaning anything unlisted is denied by default rather than silently allowed.
- **Separation of concerns:** research (fact-finding) and verification (fact-checking) are handled by independent subagents with distinct prompts and models, avoiding a single agent grading its own work.
- **Observability:** a `PostToolUse` hook persists a structured, timestamped log (`tool_log.jsonl`) of every tool call made across the agent hierarchy, including parent/child agent relationships.
- **Retrieval-augmented memory:** one MCP server exposes lookup and save tools backed by an embedded ChromaDB vector store. Lookups are semantic, conservative (a near topic is not automatically the same claim), and freshness-aware, letting the pipeline skip redundant fact-checks without serving stale verdicts.
- **Test coverage:** the pytest suite validates hook behavior and memory persistence, backed by a GitHub Actions workflow for CI.

## Tech Stack

- **Language:** Python
- **Core SDK:** Claude Agent SDK (`claude_agent_sdk`) — `ClaudeAgentOptions`, `ClaudeSDKClient`, `AgentDefinition`, `HookMatcher`, one MCP memory server
- **Async runtime:** `anyio`
- **Vector store:** ChromaDB (embedded, persistent) with a swappable embedding function
- **CI/CD:** GitHub Actions

## Repository Structure
.
├── fact_check_pipeline.py    # Multi-agent fact-checking pipeline with memory + hooks
├── memory_tools.py            # MCP tool server (check_memory / save_to_memory) backed by RAG
├── vector_store.py            # ChromaDB store: embeddings, search, thresholds, freshness
├── ingest_memory.py           # Migrate memory_store.json -> ChromaDB; --query to tune thresholds
├── hooks.py                   # PreToolUse / PostToolUse safety and logging hooks
├── tests/                      # Test suite
├── .github/workflows/          # CI configuration
└── requirements-dev.txt        # Development dependencies

## Project Milestones

1. **Tool-scoped multi-agent delegation** — a lead agent coordinates researcher and fact-checker subagents, each limited to WebSearch (`fact_check_pipeline.py`).
2. **RAG memory layer** — the single MCP server in `memory_tools.py` retrieves and saves fact-checks via the ChromaDB store in `vector_store.py`.
3. **Safety and observability hooks** — `PreToolUse`/`PostToolUse` hooks that enforce delegation policy and log every tool call (`hooks.py`).
4. **End-to-end pipeline integration** — wiring memory, hooks, and subagents together into a single fact-checking workflow with defined turn limits and tool permissions.
5. **Automated test coverage** — unit tests validating hook behavior and memory persistence (`tests/`), run in GitHub Actions.
6. **Skills** — the project as a whole demonstrates applied skills in: agentic system design (permissioning, delegation, orchestration), the Claude Agent SDK API surface (`ClaudeAgentOptions`, `ClaudeSDKClient`, `AgentDefinition`, `HookMatcher`), MCP server/tool authoring, async Python (`anyio`), retrieval-augmented generation (RAG) with ChromaDB, and test-driven validation of agent behavior backed by CI (GitHub Actions).

## Why It Matters

This project is a compact reference for the patterns needed to move AI agents from "demo" to "trustworthy system": scoped permissions, enforced delegation, audit logging, and retrieval-backed memory — the building blocks recruiters and engineering teams look for when evaluating experience with real-world agentic AI development.

## Setup: RAG Memory

```powershell
pip install -r requirements-dev.txt
python ingest_memory.py                      # one-time: import legacy memory_store.json
python ingest_memory.py --query "how long did the Taj Mahal take to build"   # inspect distances
python fact_check_pipeline.py
```

Tunable via environment variables: `FACTCHECK_MATCH_DISTANCE` (default 0.35), `FACTCHECK_RELATED_DISTANCE` (0.60), `FACTCHECK_MAX_AGE_DAYS` (90), `FACTCHECK_TOP_K` (3), `FACTCHECK_CHROMA_PATH` (`chroma_db`). The first real lookup downloads Chroma's default embedding model (~80 MB); tests use an offline fake embedder and need no download.

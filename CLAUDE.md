# CLAUDE.md

Guidance for Claude Code working in this repository.

> **Status: greenfield.** As of this writing the repo is a fresh init with no application code yet.
> This document describes the *intended* architecture agreed in planning. Treat it as the target to
> build toward, and refine it (especially the Commands and Repo Structure sections) as real code lands.

## Overview

A car-insurance comparison assistant. A user uploads their current policy as a PDF; the system
extracts the structured policy details, asks the user to fill any missing fields, researches current
Slovak-market offers, normalizes those offers to a like-for-like comparison against the user's
coverage, and produces a **switch-or-stay recommendation** — including the deterministic cancellation
(*výpoveď*) deadline computed from the policy's anniversary date and notice period.

The design is deliberately **mostly-deterministic**: a fixed LangGraph pipeline with a single real
ReAct sub-agent (market research). Agentic behavior is used only where it earns its keep; everything
else is a plain LLM call or pure Python.

## Architecture (3 layers)

```
Next.js frontend  ──HTTP/SSE──►  FastAPI backend  ──►  LangGraph app (+ SqliteSaver checkpointer)
  upload PDF                       POST /analysis          fixed graph, one ReAct sub-agent
  live agent-progress panel        GET  /analysis/{id}/stream (SSE)
  HITL form (on interrupt)         POST /analysis/{id}/resume
  final report view
```

- **Frontend — Next.js.** One page: policy-PDF upload, a chat-style panel streaming agent progress
  live, a form that appears when the graph pauses for missing info, and a final report view.
  Streaming the intermediate steps is intentional — it makes the multi-agent nature visible.
- **Backend — FastAPI.** Owns the LangGraph app and the checkpointer. Three endpoints (below).
  The SQLite checkpointer is what makes `interrupt()` survive across separate HTTP requests.
- **Graph — LangGraph.** A fixed graph with conditional edges, **not** a free-form supervisor.
  The workflow is known, so a deterministic graph is the defensible choice; the one ReAct sub-agent
  lives inside the `market_research` node.

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language (backend/graph) | Python 3.12 + `uv` | `uv` for env + dependency management |
| Orchestration | LangGraph | Fixed graph + conditional edges; one `create_react_agent` sub-agent |
| LLM framework | LangChain + Pydantic v2 | Structured outputs via Pydantic schemas |
| API | FastAPI + SSE | Async endpoints; Server-Sent Events for streaming graph events |
| Checkpointer | LangGraph `AsyncSqliteSaver` | Persists state per `thread_id`; enables `interrupt()`/resume across requests |
| LLM | Anthropic Claude | See **Claude usage** below |
| PDF intake | `pypdf` (text) + `PyMuPDF` (vision fallback) | Text-layer extraction; renders pages to images for scanned PDFs |
| Research tool | DuckDuckGo (`ddgs`, no key) | Live web search bound to the `market_research` ReAct agent |
| Frontend | Next.js 15 / React 19 / TypeScript | SSE client, upload, HITL form, report view |

## LangGraph flow

```
        ┌─────────────┐
        │ intake       │  PDF → PolicyData (text, or vision fallback for scans)
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │ validate     │──missing fields──► interrupt() ─► user ─┐
        └──────┬──────┘◄──────────────────────────────────────┘
               ▼
        ┌──────────────────┐
        │ market_research  │  ReAct agent + live web_search (DuckDuckGo)
        └──────┬───────────┘
               ▼
        ┌──────────────────┐
        │ coverage_compare │  normalize offers to like-for-like
        └──────┬───────────┘
               ▼
        ┌─────────────┐
        │ decision     │  deterministic deadline calc + LLM verdict
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │ report       │  final markdown report
        └─────────────┘
```

### Shared state

```python
class AppState(TypedDict):
    policy: PolicyData | None       # from intake
    missing_fields: list[str]       # from validate
    user_answers: dict              # from HITL resume
    market_offers: list[Offer]      # from research agent
    comparison: ComparisonTable     # from coverage_compare
    recommendation: Recommendation  # from decision
```

### Nodes

| Node | Kind | Responsibility |
|---|---|---|
| `intake` | single LLM call | PDF → `PolicyData` via structured output (vehicle, coverage limits, deductibles, premium, anniversary date, notice period). Uses extracted text; if extraction is near-empty (scanned PDF) and a real model is configured, falls back to sending rendered page images (vision). Not an agent. |
| `validate` | pure Python | Check required fields; if incomplete, `interrupt()` with the list of questions. Graph suspends → frontend renders form → `/resume` feeds answers back. |
| `market_research` | **ReAct agent** | The one real agent: `create_react_agent` + a live DuckDuckGo `web_search` tool. Researches PZP/kasko offers and extracts structured `Offer` objects. Decides its own queries; **cap at ~5 tool calls.** Slovak premiums live behind per-insurer quote forms, so live snippets are often unpriced — when nothing concretely priced is found it falls back to clearly-labelled **sample** offers. |
| `coverage_compare` | LLM call | Maps each offer onto the policy's coverage dimensions (glass, animal, deductible, limits); flags non-comparable items. Output: a table, not prose. |
| `decision` | hybrid | Deterministic Python computes the *výpoveď* deadline from anniversary date + notice period; LLM writes the switch/stay reasoning on top of the comparison. |
| `report` | assembly | Assembles everything into the final markdown report shown in the UI. |

## Human-in-the-loop & checkpointing

- The backend attaches a `SqliteSaver` checkpointer to the compiled graph. Each analysis run gets a
  `thread_id`.
- When `validate` calls `interrupt()`, the graph suspends and its state is persisted under that
  `thread_id`. The HTTP request that started the run can return; a later `POST /resume` reloads the
  checkpoint and continues. **This is why the checkpointer matters** — `interrupt()`/resume must work
  across separate HTTP requests, not within one call.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/analysis` | Start a graph run (accepts the uploaded PDF); returns `thread_id`. |
| `GET` | `/analysis/{thread_id}/stream` | SSE stream of LangGraph events for the live progress panel. |
| `POST` | `/analysis/{thread_id}/resume` | Answer the HITL questions; resume the suspended graph. |

## Proposed repo structure

Target layout (create as scaffolding lands):

```
backend/
  app.py               FastAPI app, endpoints, SSE wiring
  graph/
    build.py           Graph construction + SqliteSaver, compile
    state.py           AppState TypedDict
    nodes/             intake, validate, market_research, coverage_compare, decision, report
    tools/             web_search tool for the ReAct agent
  schemas.py           Pydantic models: PolicyData, Offer, ComparisonTable, Recommendation
frontend/              Next.js 15 app (upload, SSE progress, HITL form, report)
```

## Commands

- Install / env: `uv sync` (creates `.venv`, installs deps)
- Backend: `uv run uvicorn backend.app:app --reload` (serves on :8000; `GET /health` for a liveness check)
- Tests: `uv run pytest`
- Frontend: `cd frontend && npm install && npm run dev` (serves on :3000; proxies `/api/*` → :8000)
- Frontend build/type-check: `cd frontend && npm run build`

Runs keyless by default (stub provider). To use real Claude, set `ANTHROPIC_API_KEY` and
`LLM_PROVIDER=anthropic` in `.env` — see [README.md](README.md).

## Claude usage

- Default to a current model. Recommended: **`claude-sonnet-5`** for most nodes (intake,
  coverage_compare, the report reasoning) with structured outputs via Pydantic. Consider
  **`claude-opus-4-8`** for the harder reasoning in `decision` if quality warrants it.
- **Do not answer LLM/API questions from memory.** For model IDs, pricing, params, streaming, tool
  use, and structured outputs, consult the **`claude-api`** skill — it is the authority.
- Structured outputs are Pydantic schemas (`PolicyData`, `Offer`, `ComparisonTable`,
  `Recommendation`) — the graph passes typed objects between nodes, not free-form text.
- LLM-populated schemas inherit a small base (`_LLMExtract` in `schemas.py`) that normalizes
  placeholder strings (`'<UNKNOWN>'`, `'N/A'`, `'-'`, …) to `null` before validation — models emit
  those instead of null for fields they can't fill, and they'd otherwise crash type validation. An
  unfound field then flows into the HITL step instead of raising.

## Cost controls & runaway-agent safety

The `market_research` ReAct agent is the only unbounded-loop component, so it's the cost risk. Guard
it at **two independent layers** — belt and suspenders.

**Account layer (Anthropic Console — set manually, not in this repo):**
- Prepaid credits with **auto-reload OFF** — the worst case is losing the credits you bought, not an
  open-ended bill. A runaway loop stops when credits hit zero.
- Optionally a **workspace spend limit** as a second ceiling.
- For this project, ~$10–15 of credits with auto-reload off comfortably covers dev + demo.

**Code layer (implement in the graph):**
- **`recursion_limit`** on graph invocation (`config={"recursion_limit": N}`) — a hard cap on total
  graph super-steps; the run raises rather than looping forever.
- **~5 tool-call cap** on the `market_research` agent specifically — bound how many web searches it
  can make in one run (via a scoped recursion limit on the sub-agent and/or a tool-call counter that
  forces the agent to conclude).

When asked "how do you prevent runaway agent costs?", the answer points at both layers: an account
ceiling that can't be exceeded, and in-code limits that stop the loop before it gets there.

## Domain glossary (Slovak car insurance)

| Term | Meaning |
|---|---|
| **PZP** | *Povinné zmluvné poistenie* — mandatory third-party liability insurance. |
| **kasko** | Comprehensive (own-damage) coverage — collision, theft, glass, animal strike, etc. |
| **výpoveď** | Cancellation / termination notice sent to the insurer. |
| **anniversary date** | The policy's yearly renewal date; the reference point for cancellation timing. |
| **notice period** | Lead time before the anniversary by which *výpoveď* must be delivered. |

**Rule:** all date and deadline math is **deterministic Python**, never the LLM — dates are exactly
what LLMs get wrong.

## Conventions

- **Python:** PEP 8; type hints on public functions and node signatures; Pydantic v2 for structured
  data; deterministic nodes as pure functions; LLM-call nodes kept thin (build prompt → call → parse).
- **TypeScript:** explicit prop types; named exports; colocate component-local types.
- Keep the graph the source of truth for control flow; keep business rules (deadlines, required-field
  checks) in plain code so they're testable without the LLM.

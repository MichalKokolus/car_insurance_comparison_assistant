# CLAUDE.md

Guidance for Claude Code working in this repository.

> **Status: implemented PoC.** Backend (FastAPI + LangGraph), frontend (Next.js), and tests are all
> in the tree and runnable end-to-end, keyless, today. This document describes the actual
> architecture — keep it in sync as the code evolves rather than treating it as aspirational.

## Overview

A car-insurance comparison assistant. A user uploads their current policy as a PDF; the system
extracts the structured policy details, asks the user to fill any missing fields, researches current
Slovak-market offers, normalizes those offers to a like-for-like comparison against the user's
coverage, and produces a **switch-or-stay recommendation** — including the deterministic cancellation
(*výpoveď*) deadline computed from the policy's anniversary date and notice period.

The design is deliberately **mostly-deterministic**: a fixed LangGraph pipeline with two cooperating
ReAct sub-agents — one that researches live market offers, and a second, independent one that
fact-checks each claimed price against the evidence the first agent actually collected. Agentic
behavior is used only where it earns its keep; everything else is a plain LLM call or pure Python.

## Architecture (3 layers)

```
Next.js frontend  ──HTTP/SSE──►  FastAPI backend  ──►  LangGraph app (+ SqliteSaver checkpointer)
  upload PDF                       POST /analysis          fixed graph, two ReAct sub-agents
  live agent-progress panel        GET  /analysis/{id}/stream (SSE)
  HITL form (on interrupt)         POST /analysis/{id}/resume
  structured report view
```

- **Frontend — Next.js.** A single page (`frontend/app/page.tsx`): policy-PDF upload, a progress
  panel that streams each node as it completes (with a spinner for the in-flight step, so the UI
  never looks frozen between SSE events), a form that appears when the graph pauses for missing
  info, and the final report rendered as **structured HTML tables** (current policy, market
  comparison, web-search sources, recommendation + cancellation deadline) — not a raw markdown dump.
  Streaming the intermediate steps is intentional — it makes the multi-agent nature visible.
- **Backend — FastAPI.** Owns the LangGraph app and the checkpointer. Three endpoints (below).
  The SQLite checkpointer is what makes `interrupt()` survive across separate HTTP requests. Runs
  are tracked in an in-process `RUNS` dict keyed by `thread_id` — fine for this single-process PoC;
  a multi-worker deployment would need to move that to shared storage.
- **Graph — LangGraph.** A fixed graph with linear edges, **not** a free-form supervisor. The
  workflow is known, so a deterministic graph is the defensible choice; the two ReAct sub-agents
  live inside the `market_research` and `verify_offers` nodes — everything else is a single LLM
  call or pure Python, deliberately not agentic.

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language (backend/graph) | Python 3.12 + `uv` | `uv` for env + dependency management |
| Orchestration | LangGraph | Fixed graph, linear edges; two `create_react_agent` sub-agents |
| LLM framework | LangChain + Pydantic v2 | Structured outputs via Pydantic schemas |
| API | FastAPI + SSE (`sse-starlette`) | Async endpoints; Server-Sent Events for streaming graph events |
| Checkpointer | LangGraph `AsyncSqliteSaver` | Persists state per `thread_id`; enables `interrupt()`/resume across requests |
| LLM | Anthropic Claude | See **Claude usage** below |
| PDF intake | `pypdf` (text) + `PyMuPDF`/`pymupdf` (vision fallback) | Text-layer extraction; renders pages to images for scanned PDFs |
| Research tool | DuckDuckGo (`ddgs`, no key) | Live web search bound to the `market_research` ReAct agent; `verify_offers`' evidence-lookup tool re-checks that agent's own collected snippets |
| Frontend | Next.js 15.1 / React 19 / TypeScript 5.7 | Single page, no UI library; `EventSource` for SSE, `fetch` for POSTs |

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
        │ market_research  │  ReAct agent #1 + live web_search (DuckDuckGo)
        └──────┬───────────┘
               ▼
        ┌──────────────────┐
        │ verify_offers    │  ReAct agent #2: fact-checks offers against agent #1's own evidence
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
        │ report       │  final markdown report (kept in state; frontend builds its own tables)
        └─────────────┘
```

Edges are linear (`backend/graph/build.py`) — the only branch in the whole graph is the
`interrupt()`/resume pause inside `validate`.

### Shared state (`backend/graph/state.py`)

```python
class AppState(TypedDict, total=False):
    pdf_text: str                        # extracted text from the uploaded PDF
    pdf_b64: str                         # raw PDF (base64) — enables the vision fallback for scans
    policy: Optional[PolicyData]         # from intake / validate
    missing_fields: list[str]            # from validate
    user_answers: dict                   # from HITL resume
    market_offers: list[Offer]           # from market_research, annotated in-place by verify_offers
    research_log: list[dict]             # from market_research: queries run + URLs/snippets each returned
    comparison: Optional[ComparisonTable]  # from coverage_compare
    recommendation: Optional[Recommendation]  # from decision
    report: str                          # from report
```

### Nodes

| Node | Kind | Responsibility |
|---|---|---|
| `intake` | single LLM call | PDF → `PolicyData` via structured output (vehicle, coverage limits, deductibles, premium, anniversary date, notice period). Uses extracted text; if extraction is near-empty (scanned PDF) and a real model is configured, falls back to sending rendered page images (vision). Not an agent. |
| `validate` | pure Python | Check required fields (`anniversary_date`, `notice_period_days`); if incomplete, `interrupt()` with the list of questions. Graph suspends → frontend renders form → `/resume` feeds answers back, re-validates. |
| `market_research` | **ReAct agent #1** | `create_react_agent` + a live DuckDuckGo `web_search` tool (`backend/graph/tools/search.py`), capped by `RESEARCH_RECURSION_LIMIT = 12` (~5-6 tool calls). Researches PZP/kasko offers and extracts structured `Offer` objects. Also walks the agent's message trace to build `research_log` — each query paired with the URLs/snippets it returned — surfaced on the frontend as a "Web search sources" panel. Slovak premiums live behind per-insurer quote forms, so live snippets are often unpriced — when nothing concretely priced is found it falls back to clearly-labelled **sample** offers (`backend/data/offers.py`), with an empty `research_log` in stub mode. |
| `verify_offers` | **ReAct agent #2** | A second, independent `create_react_agent` (`backend/graph/nodes/verify_offers.py`), capped by `VERIFY_RECURSION_LIMIT = 8`. Its one tool, `check_evidence`, checks (diacritics/case-insensitive, currency/decimal-format tolerant) whether an offer's claimed insurer+premium is backed by a snippet agent #1 collected (in `research_log`), returning a graded status — `price_confirmed` / `mentioned_unconfirmed` / `no_evidence` — rather than a plain yes/no, since "insurer mentioned but price not stated" is a common, honest outcome for this market. Annotates each checkable offer's `source` with the verdict rather than dropping unconfirmed ones. Offers already labelled as sample data, or with no live evidence to check, pass through unchanged (no-op in stub mode too). |
| `coverage_compare` | LLM call (or deterministic in stub mode) | Maps each offer onto the policy's coverage dimensions (glass, animal, deductible, limits); flags non-comparable items. Stub/deterministic path uses `backend.logic.build_comparison`. Output: a table, not prose. |
| `decision` | hybrid | `backend.deadlines.compute_cancellation_deadline` (pure Python) computes the *výpoveď* deadline from anniversary date + notice period; an LLM (or `backend.logic.build_recommendation` in stub mode) writes the switch/stay reasoning on top of the comparison. The deadline and its note are always overwritten by the deterministic value afterward — never trusted from the LLM. |
| `report` | assembly | Assembles everything into a final markdown string, stored on `state["report"]`. The `/stream` endpoint's `report` SSE event also includes the structured `policy` and `comparison` objects so the frontend renders real HTML tables instead of the markdown. |

## Human-in-the-loop & checkpointing

- The backend attaches an `AsyncSqliteSaver` checkpointer to the compiled graph (`backend/app.py`
  lifespan). Each analysis run gets a `thread_id`.
- When `validate` calls `interrupt()`, the graph suspends and its state is persisted under that
  `thread_id`. The HTTP request that started the run can return; a later `POST /resume` reloads the
  checkpoint and continues via `Command(resume=answers)`. **This is why the checkpointer matters** —
  `interrupt()`/resume must work across separate HTTP requests, not within one call.

### Endpoints (`backend/app.py`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check; returns the active provider name (`"stub"` or `"anthropic"`). |
| `POST` | `/analysis` | Accepts the uploaded PDF, extracts text, mints a `thread_id`, stores the initial graph input in `RUNS`. |
| `GET` | `/analysis/{thread_id}/stream` | SSE stream of LangGraph events (`update`, `interrupt`, `report`, `done`, `error`) for the live progress panel. |
| `POST` | `/analysis/{thread_id}/resume` | Stores the HITL answers as the pending resume for that thread; client reconnects to `/stream` to continue. |

## Repo structure

```
backend/
  app.py                 FastAPI app, endpoints, SSE wiring, RUNS registry
  config.py               pydantic-settings Settings (env)
  deadlines.py            compute_cancellation_deadline() — pure, unit-tested
  logic.py                 deterministic comparison + recommendation building (stub path & shared helpers)
  pdf.py                   extract_text() + render_pdf_to_images() (vision fallback)
  schemas.py               Pydantic v2: PolicyData, Offer, OfferVerification, ComparisonTable, Recommendation + API models
  data/
    offers.py               canned Slovak-market offers fixture (+ sample_offers() relabeling, SAMPLE_SOURCE_LABEL)
  graph/
    build.py                 StateGraph construction + RECURSION_LIMIT, compile with checkpointer
    state.py                 AppState TypedDict
    nodes/                   intake, validate, market_research, verify_offers, coverage_compare, decision, report
    tools/
      search.py               web_search tool (ddgs/DuckDuckGo) for the market_research ReAct agent
  services/llm/
    base.py                  LLMProvider Protocol
    anthropic_provider.py     wraps langchain_anthropic.ChatAnthropic
    stub_provider.py          deterministic canned PolicyData (comparison/recommendation come from logic.py)
    factory.py                get_provider() — key present & not forced-stub → Anthropic, else stub
frontend/
  app/
    page.tsx                 the whole UI: upload, SSE client, progress panel, HITL form, report tables
    layout.tsx
    globals.css
  Dockerfile
tests/
  test_deadline.py           deadline math
  test_graph_stub.py         run graph in stub mode → hits interrupt → resume → Recommendation
  test_schemas.py            _LLMExtract sentinel-to-null normalization
  test_verify_offers.py      verify_offers stub passthrough + evidence-matching helpers
docker-compose.yml         whole-stack run (backend + frontend, SQLite volume, no DB service)
pyproject.toml / uv.lock
```

## Commands

- Install / env: `uv sync` (creates `.venv`, installs deps)
- Backend: `uv run uvicorn backend.app:app --reload` (serves on :8000; `GET /health` for a liveness check)
- Tests: `uv run pytest`
- Frontend: `cd frontend && npm install && npm run dev` (serves on :3000; proxies `/api/*` → :8000)
- Frontend build/type-check: `cd frontend && npm run build`
- Whole stack via Docker: `docker compose up --build` (:3000 frontend, :8000 backend, no DB container —
  the checkpointer is a SQLite file on a named volume)

Runs keyless by default (stub provider). To use real Claude, set `ANTHROPIC_API_KEY` and
`LLM_PROVIDER=anthropic` in `.env` — see [README.md](README.md).

> **Don't collide `npm run build` with a running `npm run dev`.** Both write to `frontend/.next`;
> running a production build while the dev server has that directory open can corrupt its webpack
> module cache and produce a `Cannot find module './NNN.js'` runtime error on next reload. If that
> happens: stop the dev server, `rm -rf frontend/.next`, restart `npm run dev`. Prefer `tsc --noEmit`
> or just reading the dev server's own output for type-checking while it's running.

## Claude usage

- Default to a current model. Recommended: **`claude-sonnet-5`** for most nodes (intake,
  coverage_compare, the report reasoning) with structured outputs via Pydantic. Consider
  **`claude-opus-4-8`** for the harder reasoning in `decision` if quality warrants it.
- **Do not answer LLM/API questions from memory.** For model IDs, pricing, params, streaming, tool
  use, and structured outputs, consult the **`claude-api`** skill — it is the authority.
- Structured outputs are Pydantic schemas (`PolicyData`, `Offer`, `OfferVerification`,
  `ComparisonTable`, `Recommendation`) — the graph passes typed objects between nodes, not free-form
  text.
- LLM-populated schemas inherit a small base (`_LLMExtract` in `schemas.py`) that normalizes
  placeholder strings (`'<UNKNOWN>'`, `'N/A'`, `'-'`, …) to `null` before validation — models emit
  those instead of null for fields they can't fill, and they'd otherwise crash type validation. An
  unfound field then flows into the HITL step instead of raising.

## Cost controls & runaway-agent safety

`market_research` and `verify_offers` are the only unbounded-loop components, so they're the cost
risk. Guard them at **two independent layers** — belt and suspenders.

**Account layer (Anthropic Console — set manually, not in this repo):**
- Prepaid credits with **auto-reload OFF** — the worst case is losing the credits you bought, not an
  open-ended bill. A runaway loop stops when credits hit zero.
- Optionally a **workspace spend limit** as a second ceiling.
- For this project, ~$10–15 of credits with auto-reload off comfortably covers dev + demo.

**Code layer (implemented in the graph):**
- **`RECURSION_LIMIT = 25`** (`backend/graph/build.py`), passed as `config={"recursion_limit": ...}`
  on every graph invocation — a hard cap on total graph super-steps; the run raises rather than
  looping forever.
- **`RESEARCH_RECURSION_LIMIT = 12`** (`backend/graph/nodes/market_research.py`), scoped to just the
  research sub-agent's `agent.ainvoke(...)` call — bounds it to roughly 5-6 tool calls (each ReAct
  step is ~2 super-steps).
- **`VERIFY_RECURSION_LIMIT = 8`** (`backend/graph/nodes/verify_offers.py`), the same pattern scoped
  to the fact-checking sub-agent's own tool-call loop.

When asked "how do you prevent runaway agent costs?", the answer points at both layers: an account
ceiling that can't be exceeded, and per-agent in-code limits that stop each loop before it gets there.

## Domain glossary (Slovak car insurance)

| Term | Meaning |
|---|---|
| **PZP** | *Povinné zmluvné poistenie* — mandatory third-party liability insurance. |
| **kasko** | Comprehensive (own-damage) coverage — collision, theft, glass, animal strike, etc. |
| **výpoveď** | Cancellation / termination notice sent to the insurer. |
| **anniversary date** | The policy's yearly renewal date; the reference point for cancellation timing. |
| **notice period** | Lead time before the anniversary by which *výpoveď* must be delivered. |

**Rule:** all date and deadline math is **deterministic Python** (`backend/deadlines.py`), never the
LLM — dates are exactly what LLMs get wrong.

## Conventions

- **Python:** PEP 8; type hints on public functions and node signatures; Pydantic v2 for structured
  data; deterministic nodes as pure functions; LLM-call nodes kept thin (build prompt → call → parse).
- **TypeScript:** explicit prop types; named exports; colocate component-local types.
- Keep the graph the source of truth for control flow; keep business rules (deadlines, required-field
  checks) in plain code (`backend/deadlines.py`, `backend/logic.py`) so they're testable without the LLM.

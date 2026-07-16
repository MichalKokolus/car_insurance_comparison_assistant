# Car Insurance Comparison Assistant

A PoC that reads a car-insurance policy PDF, asks for any missing details, researches current
Slovak-market offers, normalizes them to a like-for-like comparison, and returns a **switch-or-stay**
recommendation — including the deterministic cancellation (*výpoveď*) deadline.

It runs a fixed **LangGraph** pipeline with one real ReAct sub-agent, behind a **FastAPI** backend
(SSE streaming + a SQLite checkpointer for human-in-the-loop), with a minimal **Next.js** frontend.

> Architecture details, node responsibilities, and the domain glossary live in
> [CLAUDE.md](CLAUDE.md).

## Runs with no API key

The app ships with a **stub LLM provider**, so the entire flow works today without any credentials —
the analysis content is deterministic placeholder data. Add an Anthropic key (below) to switch to
real Claude; no code changes.

```
Next.js (:3000) ──/api proxy──► FastAPI (:8000) ──► LangGraph (+ SqliteSaver checkpointer)
   upload PDF                     POST /analysis         intake → validate → market_research
   live progress (SSE)            GET  /analysis/{id}/stream   → coverage_compare → decision → report
   HITL form on interrupt         POST /analysis/{id}/resume
```

## Backend setup

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync                        # create .venv and install dependencies
cp .env.example .env           # optional — defaults already run in stub mode
uv run uvicorn backend.app:app --reload   # http://localhost:8000
```

Verify it's up: `curl http://localhost:8000/health` → `{"status":"ok","provider":"stub"}`.

Run the tests:

```bash
uv run pytest
```

## Frontend setup

Prerequisites: Node 18+. With the backend running on :8000:

```bash
cd frontend
npm install
npm run dev                    # http://localhost:3000
```

`frontend/next.config.mjs` proxies `/api/*` to the backend, so the browser talks to a single origin
(which keeps SSE simple). Then: upload any PDF → watch the steps stream → fill the missing-fields
form when it appears → read the report.

## Run with Docker (whole stack)

Requires Docker Desktop. From the repo root:

```bash
docker compose up --build
```

Frontend on http://localhost:3000, backend on http://localhost:8000. The frontend waits for the
backend's healthcheck before starting.

To run against real Claude, pass the env through (or put them in a root `.env` that compose reads):

```bash
LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... docker compose up --build
```

**No database container.** The LangGraph checkpointer is SQLite — an embedded file, not a server —
so it lives in the backend container on the `checkpoints` named volume (persists across restarts).
A separate DB service is only needed if you migrate to the Postgres checkpointer.

## Switching to real Claude

Get an Anthropic API key, then in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
LLM_PROVIDER=anthropic
MODEL=claude-sonnet-5
```

Restart the backend. Now `intake`, `coverage_compare`, and `decision` call real Claude, and
`market_research` runs the ReAct agent over the `web_search` tool. Everything else is identical —
that swap is the whole point of the [`LLMProvider`](backend/services/llm/base.py) abstraction.

## Cost controls (runaway-agent safety)

Two independent layers, per CLAUDE.md:

- **Account layer** (Anthropic Console, manual): prepaid credits with **auto-reload OFF** is a hard
  ceiling; a runaway loop stops when credits hit zero. Optionally add a workspace spend limit.
- **Code layer**: a graph-level `RECURSION_LIMIT` ([backend/graph/build.py](backend/graph/build.py))
  plus a scoped `~5 tool-call` cap on the research agent
  ([backend/graph/nodes/market_research.py](backend/graph/nodes/market_research.py)).

## Layout

```
backend/        FastAPI app, LangGraph graph, Pydantic schemas, LLM provider service
frontend/       Minimal Next.js 15 app (one page: upload / progress / HITL form / report)
tests/          Deadline math + a stub-mode interrupt/resume smoke test
```

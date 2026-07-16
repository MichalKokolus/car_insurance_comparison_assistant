# Frontend — Car Insurance Comparison Assistant

Minimal Next.js 15 (App Router) client. One page: upload a policy PDF, watch graph progress stream
live over SSE, answer the human-in-the-loop form when the graph pauses, and read the final report.

## Setup

Requires Node 18+ and the backend running on `http://localhost:8000` (see the root
[README](../README.md)).

```bash
npm install
npm run dev      # http://localhost:3000
```

## How it talks to the backend

`next.config.mjs` rewrites `/api/:path*` → `http://localhost:8000/:path*`, so the browser uses one
origin. Override the target with `BACKEND_URL` if the backend runs elsewhere:

```bash
BACKEND_URL=http://localhost:9000 npm run dev
```

The page ([app/page.tsx](app/page.tsx)) drives the flow:

1. `POST /api/analysis` (file upload) → `thread_id`
2. `EventSource('/api/analysis/{thread_id}/stream')` → `update` / `interrupt` / `report` / `done`
3. On `interrupt`: render the questions, then `POST /api/analysis/{thread_id}/resume` and reopen the
   stream to continue.

## Build

```bash
npm run build
```

"""FastAPI app: start an analysis, stream graph progress (SSE), resume after human input.

The graph is compiled once in the lifespan with an AsyncSqliteSaver checkpointer — that persistence
per `thread_id` is what lets interrupt()/resume work across separate HTTP requests.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.config import get_settings
from backend.graph.build import RECURSION_LIMIT, build_graph
from backend.pdf import extract_text
from backend.schemas import ResumeRequest, StartResponse
from backend.services.llm.factory import get_provider

# In-process registry of pending runs. Single-process PoC; a multi-worker deployment would move
# this to shared storage (the checkpointer already holds the graph state itself).
RUNS: dict[str, dict[str, Any]] = {}

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db) as saver:
        app.state.graph = build_graph(saver)
        yield


app = FastAPI(title="Car Insurance Comparison Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _jsonable(obj: Any) -> Any:
    """Recursively convert Pydantic models (and containers of them) to JSON-safe values."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {key: _jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(value) for value in obj]
    return obj


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "provider": get_provider().name}


@app.post("/analysis", response_model=StartResponse)
async def start_analysis(file: UploadFile = File(...)) -> StartResponse:
    data = await file.read()
    text = extract_text(data)
    thread_id = uuid.uuid4().hex
    RUNS[thread_id] = {"input": {"pdf_text": text, "user_answers": {}}}
    return StartResponse(thread_id=thread_id)


@app.post("/analysis/{thread_id}/resume")
async def resume_analysis(thread_id: str, body: ResumeRequest) -> dict:
    if thread_id not in RUNS:
        raise HTTPException(status_code=404, detail="unknown thread_id")
    RUNS[thread_id]["resume"] = body.answers
    return {"ok": True}


@app.get("/analysis/{thread_id}/stream")
async def stream_analysis(thread_id: str, request: Request) -> EventSourceResponse:
    graph = request.app.state.graph
    run = RUNS.get(thread_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown thread_id")

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    if "resume" in run:
        payload: Any = Command(resume=run.pop("resume"))
    else:
        payload = run.get("input")

    async def event_generator():
        try:
            async for chunk in graph.astream(payload, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt = chunk["__interrupt__"][0]
                    yield {"event": "interrupt", "data": json.dumps(_jsonable(interrupt.value))}
                    return
                for node, update in chunk.items():
                    yield {
                        "event": "update",
                        "data": json.dumps({"node": node, "state": _jsonable(update)}),
                    }

            snapshot = await graph.aget_state(config)
            values = snapshot.values
            yield {
                "event": "report",
                "data": json.dumps(
                    {
                        "report": values.get("report", ""),
                        "recommendation": _jsonable(values.get("recommendation")),
                    }
                ),
            }
            yield {"event": "done", "data": "{}"}
        except Exception as exc:  # surface errors to the client instead of a silent stream close
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(event_generator())

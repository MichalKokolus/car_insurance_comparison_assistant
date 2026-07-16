"""End-to-end graph test in stub mode: run to the HITL interrupt, resume, get a recommendation."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from backend.graph.build import RECURSION_LIMIT, build_graph


async def test_interrupt_then_resume_produces_recommendation():
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test-1"}, "recursion_limit": RECURSION_LIMIT}

    # Phase 1: run until the graph pauses for missing fields.
    interrupt_value = None
    async for chunk in graph.astream(
        {"pdf_text": "sample policy text", "user_answers": {}},
        config=config,
        stream_mode="updates",
    ):
        if "__interrupt__" in chunk:
            interrupt_value = chunk["__interrupt__"][0].value

    assert interrupt_value is not None
    assert "anniversary_date" in interrupt_value["missing_fields"]
    assert "notice_period_days" in interrupt_value["missing_fields"]

    # Phase 2: resume with the answers and let it run to completion.
    answers = {"anniversary_date": "2025-09-01", "notice_period_days": 42}
    async for _ in graph.astream(Command(resume=answers), config=config, stream_mode="updates"):
        pass

    state = await graph.aget_state(config)
    rec = state.values["recommendation"]
    assert rec is not None
    assert rec.verdict in ("switch", "stay")
    assert rec.cancellation_deadline is not None  # deterministic, from the resumed answers
    assert state.values["report"].startswith("# Car insurance comparison report")

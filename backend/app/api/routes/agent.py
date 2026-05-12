"""Agent API surface.

- `POST /run`     — blocks until the agent finishes; returns the full AgentRun.
- `POST /stream`  — Server-Sent Events stream of each step as it lands.
- `GET  /tools`   — introspect what tools the orchestrator currently has.

Persistence + resume come in Phase 8 (Postgres-backed agent_runs / agent_steps)."""

from __future__ import annotations

import json
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.llm import AnthropicClient
from app.agent.models import AgentRun, AgentRunStatus, StepKind
from app.agent.prompts import ORCHESTRATOR_SYSTEM
from app.agent.runner import AgentRunner
from app.agent.tools.dispatcher import ToolDispatcher
from app.agent.tools.financial_tools import register_financial_tools
from app.agent.tools.registry import ToolRegistry
from app.config import AGENT_MAX_ITERS, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.limiter import limiter

router = APIRouter()


# Built once per process. The registry + dispatcher are immutable after init;
# the LLM client wraps an httpx pool so we want a single instance.
_registry = ToolRegistry()
register_financial_tools(_registry)
_dispatcher = ToolDispatcher(_registry)
_llm: Optional[AnthropicClient] = None


def _get_llm() -> AnthropicClient:
    global _llm
    if _llm is None:
        if not ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="ANTHROPIC_API_KEY not configured. Set it in backend/.env to use /api/agent/*.",
            )
        _llm = AnthropicClient(api_key=ANTHROPIC_API_KEY, default_model=ANTHROPIC_MODEL)
    return _llm


def _make_runner() -> AgentRunner:
    return AgentRunner(
        llm=_get_llm(),
        registry=_registry,
        dispatcher=_dispatcher,
        system=ORCHESTRATOR_SYSTEM,
        max_iters=AGENT_MAX_ITERS,
    )


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    model: Optional[str] = None


@router.post("/run", response_model=AgentRun)
@limiter.limit("5/minute")
async def run_agent(request: Request, req: AgentRunRequest) -> AgentRun:
    return await _make_runner().run(req.query, model=req.model)


@router.post("/stream")
@limiter.limit("5/minute")
async def stream_agent(request: Request, req: AgentRunRequest) -> StreamingResponse:
    runner = _make_runner()

    async def event_source() -> AsyncIterator[bytes]:
        try:
            async for step, run in runner.stream(req.query, model=req.model):
                yield _sse_event(step.kind.value, _step_payload(step)).encode()
                if step.kind in (StepKind.FINAL, StepKind.ERROR):
                    yield _sse_event("done", _run_summary(run)).encode()
                    return
        except Exception as exc:                                       # noqa: BLE001
            yield _sse_event("error", {"error": f"{type(exc).__name__}: {exc}"}).encode()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tools")
async def list_tools() -> dict:
    """Inspect what tools the orchestrator currently has access to."""
    return {"tools": _registry.anthropic_schemas()}


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse_event(event: str, data: dict) -> str:
    """SSE wire format: `event:` line + `data:` line + blank line terminator."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _step_payload(step) -> dict:
    """Convert a step to a JSON-friendly dict. mode='json' converts enums + datetimes."""
    return step.model_dump(mode="json")


def _run_summary(run: AgentRun) -> dict:
    """The tail event that callers use to know the stream is closed cleanly."""
    return {
        "id":                  run.id,
        "status":              run.status.value if isinstance(run.status, AgentRunStatus) else str(run.status),
        "final_text":          run.final_text,
        "total_cost_usd":      run.total_cost_usd,
        "total_latency_ms":    run.total_latency_ms,
        "total_input_tokens":  run.total_input_tokens,
        "total_output_tokens": run.total_output_tokens,
        "error":               run.error,
    }

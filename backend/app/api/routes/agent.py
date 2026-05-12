"""Agent API surface. Phase 7 MVP — single sync endpoint that runs the loop
to completion and returns the full AgentRun. Streaming + persistence come
in subsequent commits."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.agent.llm import AnthropicClient
from app.agent.models import AgentRun
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


class AgentRunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    model: Optional[str] = None


@router.post("/run", response_model=AgentRun)
@limiter.limit("5/minute")
async def run_agent(request: Request, req: AgentRunRequest) -> AgentRun:
    runner = AgentRunner(
        llm=_get_llm(),
        registry=_registry,
        dispatcher=_dispatcher,
        system=ORCHESTRATOR_SYSTEM,
        max_iters=AGENT_MAX_ITERS,
    )
    return await runner.run(req.query, model=req.model)


@router.get("/tools")
async def list_tools() -> dict:
    """Inspect what tools the orchestrator currently has access to."""
    return {"tools": _registry.anthropic_schemas()}

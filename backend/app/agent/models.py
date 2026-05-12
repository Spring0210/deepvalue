from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_ms() -> int:
    return int(time.time() * 1000)


class LLMUsage(BaseModel):
    model:               str
    input_tokens:        int = 0
    output_tokens:       int = 0
    cache_read_tokens:   int = 0   # Anthropic prompt-cache hits
    cache_write_tokens:  int = 0   # Anthropic prompt-cache writes
    cost_usd:            float = 0.0
    latency_ms:          int = 0


class ToolCall(BaseModel):
    """One tool invocation requested by the LLM in a single assistant turn."""
    id:    str                       # Anthropic tool_use_id, used to match tool_result back
    name:  str
    args:  dict[str, Any]


class ToolResult(BaseModel):
    """Result of dispatching a ToolCall. Never raises — failures encoded as error."""
    call_id:    str
    name:       str
    ok:         bool
    output:     Optional[Any] = None
    error:      Optional[str] = None
    latency_ms: int = 0
    attempts:   int = 1


class StepKind(str, Enum):
    LLM        = "llm"           # one assistant turn (with thought + maybe tool_calls)
    TOOL_BATCH = "tool_batch"    # parallel dispatch of one or more tools
    FINAL      = "final"         # terminal answer
    ERROR      = "error"         # unrecoverable failure
    REPAIR     = "repair"        # corrective user message after structured-output parse failure


class AgentStep(BaseModel):
    """One step in an agent run. Flat schema so each row maps to one persisted record."""
    idx:        int
    kind:       StepKind
    started_at: int = Field(default_factory=_now_ms)

    # LLM step
    text:       Optional[str] = None            # assistant message text (if any)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage:      Optional[LLMUsage] = None

    # Tool batch step
    tool_results: list[ToolResult] = Field(default_factory=list)

    # Error step
    error: Optional[str] = None


class AgentRunStatus(str, Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CAPPED    = "capped"        # hit iteration cap


class AgentRun(BaseModel):
    id:         str = Field(default_factory=_new_id)
    query:      str
    status:     AgentRunStatus = AgentRunStatus.RUNNING
    started_at: int = Field(default_factory=_now_ms)
    finished_at: Optional[int] = None

    steps:      list[AgentStep] = Field(default_factory=list)
    final_text: Optional[str] = None
    structured_output: Optional[dict[str, Any]] = None   # populated when output_schema is set

    total_cost_usd:   float = 0.0
    total_latency_ms: int = 0
    total_input_tokens:  int = 0
    total_output_tokens: int = 0

    error: Optional[str] = None

    def append(self, step: AgentStep) -> None:
        self.steps.append(step)
        if step.usage:
            self.total_cost_usd      += step.usage.cost_usd
            self.total_input_tokens  += step.usage.input_tokens
            self.total_output_tokens += step.usage.output_tokens

    def finish(self, status: AgentRunStatus, final_text: Optional[str] = None, error: Optional[str] = None) -> None:
        self.status = status
        self.final_text = final_text
        self.error = error
        self.finished_at = _now_ms()
        self.total_latency_ms = self.finished_at - self.started_at

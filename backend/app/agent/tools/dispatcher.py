from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import ValidationError

from app.agent.models import ToolCall, ToolResult
from app.agent.tools.registry import ToolRegistry, ToolSpec


class ToolDispatcher:
    """Executes ToolCalls. Never raises — failures land in ToolResult.error.

    Each call runs in its own task with `asyncio.wait_for` for timeout, plus
    exponential backoff retry on transient errors (TimeoutError + raw Exception).
    A batch is dispatched in parallel via `asyncio.gather`."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def dispatch_many(self, calls: list[ToolCall]) -> list[ToolResult]:
        return await asyncio.gather(*(self._dispatch_one(c) for c in calls))

    async def _dispatch_one(self, call: ToolCall) -> ToolResult:
        t0 = time.perf_counter()
        try:
            spec = self._registry.get(call.name)
        except KeyError as exc:
            return ToolResult(
                call_id=call.id, name=call.name, ok=False,
                error=str(exc), latency_ms=_elapsed_ms(t0),
            )

        try:
            args = self._registry.validate_args(call.name, call.args)
        except ValidationError as exc:
            return ToolResult(
                call_id=call.id, name=call.name, ok=False,
                error=f"Invalid arguments: {exc.errors()}",
                latency_ms=_elapsed_ms(t0),
            )

        return await self._run_with_retry(spec, call, args, t0)

    async def _run_with_retry(
        self, spec: ToolSpec, call: ToolCall, args: Any, t0: float,
    ) -> ToolResult:
        last_err: str = "unknown error"
        for attempt in range(1, spec.max_retries + 2):
            try:
                output = await asyncio.wait_for(spec.handler(args), timeout=spec.timeout_s)
                return ToolResult(
                    call_id=call.id, name=call.name, ok=True,
                    output=output, latency_ms=_elapsed_ms(t0), attempts=attempt,
                )
            except asyncio.TimeoutError:
                last_err = f"timeout after {spec.timeout_s}s"
            except Exception as exc:                                # noqa: BLE001
                last_err = f"{type(exc).__name__}: {exc}"
            if attempt <= spec.max_retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 4))     # 1s, 2s, 4s cap

        return ToolResult(
            call_id=call.id, name=call.name, ok=False,
            error=last_err, latency_ms=_elapsed_ms(t0),
            attempts=spec.max_retries + 1,
        )


def _elapsed_ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)

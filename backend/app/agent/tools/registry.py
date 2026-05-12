from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel

# An async tool handler: validated args in, JSON-serializable result out.
ToolHandler = Callable[[BaseModel], Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    name:         str
    description:  str
    args_model:   Type[BaseModel]
    handler:      ToolHandler
    timeout_s:    float = 20.0
    max_retries:  int   = 2          # total attempts = max_retries + 1


class ToolRegistry:
    """Holds all tools available to the agent.

    Exposes schemas in the Anthropic tool_use shape and dispatches a validated
    call to the registered handler. Schemas are derived from Pydantic models so
    we never hand-write JSON Schema."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name:         str,
        description:  str,
        args_model:   Type[BaseModel],
        handler:      ToolHandler,
        timeout_s:    float = 20.0,
        max_retries:  int   = 2,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered.")
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            args_model=args_model,
            handler=handler,
            timeout_s=timeout_s,
            max_retries=max_retries,
        )

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Unknown tool '{name}'.")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def anthropic_schemas(self) -> list[dict[str, Any]]:
        """Return tools in the shape Anthropic's Messages API expects."""
        out: list[dict[str, Any]] = []
        for spec in self._tools.values():
            schema = spec.args_model.model_json_schema()
            # Anthropic wants {name, description, input_schema}
            out.append({
                "name":         spec.name,
                "description":  spec.description,
                "input_schema": _strip_pydantic_extras(schema),
            })
        return out

    def validate_args(self, name: str, raw: dict[str, Any]) -> BaseModel:
        spec = self.get(name)
        return spec.args_model.model_validate(raw)


def _strip_pydantic_extras(schema: dict[str, Any]) -> dict[str, Any]:
    """Anthropic accepts standard JSON Schema; drop Pydantic-specific keys it ignores."""
    cleaned = {k: v for k, v in schema.items() if k != "title"}
    if "properties" in cleaned:
        cleaned["properties"] = {
            field: {k: v for k, v in defn.items() if k != "title"}
            for field, defn in cleaned["properties"].items()
        }
    return cleaned

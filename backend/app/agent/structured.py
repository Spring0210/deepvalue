"""Structured-output enforcement for agent runs.

When the runner is constructed with an `output_schema`, the agent's final
answer must parse as JSON and validate against that Pydantic model. If it
doesn't, the runner sends the validation error back to the model and asks
for a corrected attempt (up to `max_repairs` times)."""

from __future__ import annotations

import json
from typing import Type

from pydantic import BaseModel, ValidationError


class StructuredOutputError(Exception):
    """Raised by `parse_structured` when the model's reply fails JSON parse or
    schema validation. Carries the raw cleaned text so the runner can decide
    whether to log it or feed it back in for repair."""

    def __init__(self, message: str, raw: str) -> None:
        super().__init__(message)
        self.raw = raw


def parse_structured(text: str, schema: Type[BaseModel]) -> BaseModel:
    """Strip optional ``` fences, parse as JSON, validate against `schema`."""
    cleaned = _strip_fences(text or "")
    if not cleaned:
        raise StructuredOutputError(
            "Empty response. Reply with a single JSON object matching the schema.",
            raw=cleaned,
        )
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            f"Could not parse JSON: {exc.msg} (line {exc.lineno}, col {exc.colno}). "
            "Reply with a single JSON object only — no prose, no code fences.",
            raw=cleaned,
        ) from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"JSON did not match the required schema: {exc.errors()}",
            raw=cleaned,
        ) from exc


def schema_hint(schema: Type[BaseModel]) -> str:
    """System-prompt addendum that tells the model what shape to produce."""
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    return (
        "\n\n# Output format\n"
        "When you finish (a response with no tool calls), reply with a SINGLE "
        "JSON object that conforms to the JSON Schema below. No prose, no "
        "markdown, no code fences — just the JSON object.\n\n"
        f"JSON Schema:\n{schema_json}"
    )


def _strip_fences(text: str) -> str:
    """Tolerate ```json ... ``` and ``` ... ``` wrappers some models emit."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    lines = lines[1:]  # drop opening fence (```json or ```)
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()

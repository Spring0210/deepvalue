"""Shared pytest fixtures. Kept tiny — most tests don't need anything.

Notable: we set ANTHROPIC_API_KEY to a dummy value so importing app.config
during a test run never prints the warning banner. No real network calls
should happen in tests."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")

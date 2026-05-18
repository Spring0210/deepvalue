import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_RECOMMENDATION_MODEL: str = os.getenv("GROQ_RECOMMENDATION_MODEL", "llama-3.3-70b-versatile")

# Anthropic Claude — powers the v0.5 agent harness and (when set) the chat + recommendation streams.
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL:   str = os.getenv("ANTHROPIC_MODEL",   "claude-sonnet-4-5")
AGENT_MAX_ITERS:   int = int(os.getenv("AGENT_MAX_ITERS", "8"))

# Chat / recommendation models. Anthropic preferred when ANTHROPIC_API_KEY is set;
# otherwise the code falls back to Groq automatically.
ANTHROPIC_CHAT_MODEL: str = os.getenv("ANTHROPIC_CHAT_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_RECO_MODEL: str = os.getenv("ANTHROPIC_RECO_MODEL", "claude-sonnet-4-5")

# Override to "groq" to force the Groq path even with an Anthropic key present.
CHAT_PROVIDER: str = os.getenv("CHAT_PROVIDER", "anthropic" if ANTHROPIC_API_KEY else "groq").lower()

# Comma-separated list of allowed CORS origins.
# Falls back to localhost dev server if not set.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

if not GROQ_API_KEY and not ANTHROPIC_API_KEY:
    print("WARNING: neither GROQ_API_KEY nor ANTHROPIC_API_KEY is set — chat & recommendation streams will error.")
elif not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY is not set. /api/agent/* endpoints will return 503; chat/reco will use Groq.")
elif not GROQ_API_KEY:
    print("INFO: GROQ_API_KEY is not set. Chat/recommendation will use Anthropic only (no Groq fallback).")

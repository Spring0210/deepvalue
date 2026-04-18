import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_RECOMMENDATION_MODEL: str = os.getenv("GROQ_RECOMMENDATION_MODEL", "llama-3.3-70b-versatile")

# Comma-separated list of allowed CORS origins.
# Falls back to localhost dev server if not set.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set. Chat functionality will not work.")

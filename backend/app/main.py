from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.routes import stock, chat, agent
from app.services.rag import init_rag
from app.config import ALLOWED_ORIGINS
from app.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build FAISS index on startup (runs once, saved to disk)
    init_rag()
    yield


app = FastAPI(
    title="Buffett AI Analyzer API",
    version="1.0.0",
    description="Warren Buffett financial ratio engine + RAG chat backend",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router, prefix="/api/stock", tags=["stock"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(agent.router, prefix="/api/agent", tags=["agent"])


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}

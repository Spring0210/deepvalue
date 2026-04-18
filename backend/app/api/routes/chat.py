from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.rag import stream_chat

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    ticker: str = ""
    ratios: list[dict] = []
    history: list[dict] = []   # [{role: "user"|"assistant", content: str}, ...]


@router.post("")
def chat(request: ChatRequest):
    """Stream an LLM response with RAG context and full conversation history."""
    return StreamingResponse(
        stream_chat(request.question, request.ticker, request.ratios, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

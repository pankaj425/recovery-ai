from __future__ import annotations

from fastapi import APIRouter

from app.agents.orchestrator import handle_chat
from app.api.deps import DBSession, CurrentUser
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/ai", tags=["ai-assistant"])


@router.post("/chat", response_model=ChatResponse, summary="Merchant AI assistant (tool-calling agent)")
def chat(payload: ChatRequest, db: DBSession, user: CurrentUser) -> ChatResponse:
    result = handle_chat(db, payload.message)
    return ChatResponse(**result)

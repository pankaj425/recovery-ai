from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500, examples=["Which customers should I prioritize today?"])


class ChatMetric(BaseModel):
    label: str
    value: str | float | int


class ChatResponse(BaseModel):
    answer: str
    metrics: list[ChatMetric] = []
    insights: list[str] = []
    recommendations: list[str] = []
    intent: str
    tools_used: list[str] = []

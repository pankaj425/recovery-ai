"""LLM provider abstraction. Swap providers via LLM_PROVIDER env var.

The provider is used ONLY to phrase the final business narrative from
verified tool output - never to compute numbers or query data.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger("recoveryai.llm")

_SYSTEM_PROMPT = (
    "You are RecoveryAI's merchant assistant for a payment-recovery platform. "
    "You will receive: (1) the merchant's question, (2) JSON produced by backend "
    "tools (the ONLY source of truth for numbers), and (3) a draft answer. "
    "Rewrite the draft into a concise, professional answer (max 140 words). "
    "Use exactly the numbers given; NEVER invent or alter figures, customer names "
    "or probabilities. Predictions must be phrased as estimates. "
    'Respond with strict JSON: {"answer": string}.'
)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str) -> str | None:
        """Return raw completion text, or None if unavailable/failed."""


class _HTTPChatProvider(LLMProvider):
    url: str = ""
    api_key_env: str = ""
    model_setting: str = ""

    def complete(self, system: str, user: str) -> str | None:
        api_key = getattr(settings, self.api_key_env)
        model = getattr(settings, self.model_setting)
        if not api_key:
            logger.warning("%s selected but no API key configured", self.name)
            return None
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.error("%s call failed: %s", self.name, exc)
            return None


class OpenAIProvider(_HTTPChatProvider):
    name = "openai"
    url = "https://api.openai.com/v1/chat/completions"
    api_key_env = "openai_api_key"
    model_setting = "openai_model"


class GroqProvider(_HTTPChatProvider):
    name = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_key_env = "groq_api_key"
    model_setting = "groq_model"


class MockLLMProvider(LLMProvider):
    """Offline mode: signals the orchestrator to keep its deterministic draft."""

    name = "mock"

    def complete(self, system: str, user: str) -> str | None:
        return None


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "groq": GroqProvider,
    "mock": MockLLMProvider,
}


def get_llm_provider() -> LLMProvider:
    provider_cls = _PROVIDERS.get(settings.llm_provider.lower(), MockLLMProvider)
    return provider_cls()


def refine_answer(provider: LLMProvider, *, question: str, context: dict, draft: str) -> str:
    """Ask the provider to polish the deterministic draft; fall back on any failure."""
    raw = provider.complete(
        _SYSTEM_PROMPT,
        json.dumps({"question": question, "tool_output": context, "draft_answer": draft}, default=str),
    )
    if raw is None:
        return draft
    try:
        refined = json.loads(raw)
        answer = refined.get("answer")
        return answer.strip() if isinstance(answer, str) and len(answer) > 10 else draft
    except (json.JSONDecodeError, AttributeError):
        return draft

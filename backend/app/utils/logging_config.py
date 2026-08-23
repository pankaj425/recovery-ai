"""Structured logging configuration for API + agent observability."""
from __future__ import annotations

import logging
import sys


class _AgentAdapter(logging.LoggerAdapter):
    """Adds structured key=value context to agent/prediction log lines."""

    def process(self, msg, kwargs):  # noqa: ANN001
        extra = kwargs.pop("extra", {})
        ctx = " ".join(f"{k}={v}" for k, v in extra.items())
        return (f"{msg} {ctx}" if ctx else msg), kwargs


def configure_logging(level: int = logging.INFO) -> None:
    fmt = "%(asctime)s %(levelname)-7s %(name)s :: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def agent_logger(name: str = "recoveryai.agent") -> logging.LoggerAdapter:
    return _AgentAdapter(logging.getLogger(name), {})

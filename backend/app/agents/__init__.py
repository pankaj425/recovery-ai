"""Agentic AI layer: intent classification, tool calling, orchestration.

The LLM never touches the database. Every number in an answer comes from a
registered backend tool; the LLM only shapes language around tool results.
"""

"""Backward-compatible import — Groq is BYOG (guided student key), not managed proxy.

Prefer ``studio.ai.providers.groq.GroqProvider``.
"""

from studio.ai.providers.groq import GroqProvider as GroqManagedProvider

__all__ = ["GroqManagedProvider"]

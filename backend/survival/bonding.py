"""Bond (docs/superpowers/specs/2026-09-25-bond-design.md): importing this module registers every Bond job
and chore with the worker's Talker (backend.survival.talker), which imports it when it starts.

B1: the chat lane and its questions (backend.survival.talk).
"""

from __future__ import annotations

from backend.survival import talk  # noqa: F401  (the chat lane, its reply and fact questions)

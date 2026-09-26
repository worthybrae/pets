"""Mind (docs/superpowers/specs/2026-09-26-mind-and-making-design.md): importing this module registers every
Mind hook. The worker's Talker imports it when it starts.

M1: the moments Mimo remembers of its event log (backend.survival.episodes), and sleep consolidating
each game day (backend.survival.consolidation).
M2: teaching through the chat (backend.survival.teaching, with backend.survival.lessons).
"""

from __future__ import annotations

from backend.survival import consolidation  # noqa: F401  (an evening's sleep consolidates the day)
from backend.survival import episodes  # noqa: F401  (the memory mirror's moments and near death)
from backend.survival import teaching  # noqa: F401  (the chat's "teach" question, "unsure", seeing it true)

"""Mind (docs/superpowers/specs/2026-09-26-mind-and-making-design.md): importing this module registers every
Mind hook. The worker's Talker imports it when it starts, and so does the Chooser (reflection).

M1: the moments Mimo remembers of its event log (backend.survival.episodes), and sleep consolidating
each game day (backend.survival.consolidation).
M2: teaching through the chat (backend.survival.teaching, with backend.survival.lessons), replies that
remember (backend.survival.remembering), and thoughts (backend.survival.insights).
"""

from __future__ import annotations

from backend.survival import consolidation  # noqa: F401  (an evening's sleep consolidates the day)
from backend.survival import episodes  # noqa: F401  (the memory mirror's moments and near death)
from backend.survival import insights  # noqa: F401  (reflection at dusk and at night, the goal's thoughts)
from backend.survival import remembering  # noqa: F401  (a reply line from memory, rehearsed when said)
from backend.survival import teaching  # noqa: F401  (the chat's "teach" question, "unsure", seeing it true)

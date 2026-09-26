"""Mind (docs/superpowers/specs/2026-09-26-mind-and-making-design.md): importing this module registers every
Mind hook. The worker's Talker imports it when it starts.

M1: the moments Mimo remembers of its event log (backend.survival.episodes).
"""

from __future__ import annotations

from backend.survival import episodes  # noqa: F401  (the memory mirror's moments and near death)

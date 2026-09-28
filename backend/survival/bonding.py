"""Bond (docs/superpowers/specs/2026-09-25-bond-design.md): importing this module registers every Bond job
and chore with the worker's Talker (backend.survival.talker), which imports it when it starts.

B1: the chat lane and its questions (backend.survival.talk).
B2: the inbox's chores: the mirror, and Mimo's asks for care and for names (backend.survival.inbox);
the owner's requests: the chat's third question, the goal's pull and kept promises
(backend.survival.requests).
B3: the notable moments the inbox mirrors and the near-death chore (backend.survival.moments); the
story lane (backend.survival.diary).
"""

from __future__ import annotations

from backend.survival import talk  # noqa: F401  (the chat lane, its reply and fact questions)
from backend.survival import inbox  # noqa: F401  (the mirror, asks for care and for names)
from backend.survival import requests  # noqa: F401  (the request question, goals.PULLS, kept promises)
from backend.survival import moments  # noqa: F401  (first sightings, seeds, danger, near death)
from backend.survival import diary  # noqa: F401  (the story lane)
from backend.survival import questions  # noqa: F401  (W1: Mimo's questions to its owner, and their answers)
from backend.survival import wild_news  # noqa: F401  (W1: new moments for Mind, news and danger for the inbox)

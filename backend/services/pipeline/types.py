"""Data types passed between pipeline stages."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreativeBrief:
    """Output of Stage 1 (Dreamer). Pure creative vision, no coordinates."""
    vision: str
    emotional_intent: str
    inspiration_source: str | None = None


@dataclass
class BuildPhase:
    """A single phase within a build plan."""
    name: str
    description: str
    operations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BuildPlan:
    """Output of Stage 2 (Architect). Structured spatial plan."""
    project: str
    region_name: str
    region_description: str
    region_tags: list[str]
    bounds: dict[str, list[int]]  # {"min": [x,y,z], "max": [x,y,z]}
    phases: list[BuildPhase]
    relationships: dict[str, str] = field(default_factory=dict)

    def total_operations(self) -> int:
        return sum(len(p.operations) for p in self.phases)


@dataclass
class BuildReport:
    """Output of Stage 3 (Builder). What was actually placed."""
    voxels_placed: int
    phases_completed: list[str]
    phases_remaining: list[str]
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.voxels_placed > 0


@dataclass
class ReviewIssue:
    """A single issue identified by the Critic."""
    area: str
    problem: str
    suggestion: str


@dataclass
class CriticReview:
    """Output of Stage 4 (Critic). Evaluation of the build."""
    overall_assessment: str
    strengths: list[str]
    issues: list[ReviewIssue]
    next_session_priorities: list[str]
    region_status: str  # "in_progress" | "complete" | "needs_revision"

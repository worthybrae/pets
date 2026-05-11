"""Tests for pipeline data types."""

from backend.services.pipeline.types import (
    CreativeBrief, BuildPlan, BuildPhase, BuildReport, CriticReview, ReviewIssue,
)


def test_creative_brief_from_text():
    brief = CreativeBrief(
        vision="Build a terraced garden on the eastern hillside",
        emotional_intent="Nostalgic, overgrown, alive",
        inspiration_source="Owner mentioned grandmother's garden",
    )
    assert "terraced garden" in brief.vision
    assert brief.inspiration_source is not None


def test_build_plan_total_operations():
    plan = BuildPlan(
        project="Test Tower",
        region_name="Tower Site",
        region_description="A tall stone tower",
        region_tags=["tower", "stone"],
        bounds={"min": [0, 0, 0], "max": [10, 30, 10]},
        phases=[
            BuildPhase(
                name="base", description="Stone foundation",
                operations=[{"type": "fill_region", "x1": 0, "y1": 0, "z1": 0,
                             "x2": 10, "y2": 3, "z2": 10, "r": 128, "g": 128, "b": 128}],
            ),
            BuildPhase(
                name="walls", description="Tower walls",
                operations=[{"type": "place_cylinder", "cx": 5, "cz": 5,
                             "y_bottom": 3, "y_top": 25, "radius": 5,
                             "r": 160, "g": 160, "b": 160, "hollow": True}],
            ),
        ],
        relationships={"north_of": "gate"},
    )
    assert len(plan.phases) == 2
    assert plan.total_operations() == 2
    assert plan.region_tags == ["tower", "stone"]


def test_build_report():
    report = BuildReport(voxels_placed=12500, phases_completed=["base", "walls"], phases_remaining=["roof"])
    assert report.voxels_placed == 12500
    assert report.success is True


def test_build_report_with_errors():
    report = BuildReport(voxels_placed=0, phases_completed=[], phases_remaining=["base"], errors=["Region too large"])
    assert report.success is False


def test_critic_review():
    review = CriticReview(
        overall_assessment="Strong direction, needs detail",
        strengths=["good spatial placement"],
        issues=[ReviewIssue(area="walls", problem="too uniform", suggestion="add noise 20-30")],
        next_session_priorities=["wall texture"],
        region_status="in_progress",
    )
    assert len(review.issues) == 1
    assert review.region_status == "in_progress"

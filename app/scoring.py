"""Evaluation metrics and scoring aggregation for HumanEval Studio."""

from typing import Any

from app.models import FailureCategory, ReviewSubmission


def calculate_scorecard(submission: ReviewSubmission) -> dict[str, Any]:
    dimension_scores = {s.dimension: s.score for s in submission.scores}
    avg_score = (
        round(sum(dimension_scores.values()) / len(dimension_scores), 2)
        if dimension_scores
        else 0.0
    )

    # Compute penalties based on failure category severity
    critical_penalties = {
        FailureCategory.HALLUCINATION: 1.5,
        FailureCategory.INSTRUCTION_VIOLATION: 1.0,
        FailureCategory.SYCOPHANCY: 0.8,
        FailureCategory.UNGROUNDED_ASSERTION: 1.0,
        FailureCategory.REASONING_ERROR: 1.2,
        FailureCategory.UNNATURAL_TONE: 0.5,
        FailureCategory.OVER_REFUSAL: 0.7,
        FailureCategory.FORMATTING_ERROR: 0.4,
    }

    total_penalty = sum(critical_penalties.get(tag, 0.5) for tag in submission.failure_tags)
    adjusted_score = max(1.0, round(avg_score - total_penalty, 2))

    # Determine Quality Tier
    if adjusted_score >= 4.2 and not submission.failure_tags:
        tier = "HIGH_QUALITY_GOLD"
    elif adjusted_score >= 3.0:
        tier = "ACCEPTABLE"
    elif adjusted_score >= 2.0:
        tier = "NEEDS_REVISION"
    else:
        tier = "REJECTED_UNSAFE_OR_DEFECTIVE"

    return {
        "dialogue_id": submission.dialogue_id,
        "raw_average_score": avg_score,
        "adjusted_quality_score": adjusted_score,
        "quality_tier": tier,
        "failure_count": len(submission.failure_tags),
        "dimension_breakdown": dimension_scores,
        "quotes_cited": [s.evidence_quote for s in submission.scores if s.evidence_quote],
        "is_ready_for_training": tier in {"HIGH_QUALITY_GOLD", "ACCEPTABLE"},
    }

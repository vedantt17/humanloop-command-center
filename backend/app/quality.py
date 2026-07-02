from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Contributor, EvaluationTask, HumanRating, Project, QAReview, QualityFlag


CATEGORY_LABELS = {
    "missing_rating": "Missing human rating",
    "duplicate_prompt": "Duplicate prompt",
    "inconsistent_scoring": "Inconsistent rubric score",
    "low_effort_comment": "Low-effort reviewer comment",
    "contributor_drift": "Contributor drift",
    "fast_submission": "Unusually fast submission",
    "high_rejection_contributor": "High rejection-rate contributor",
    "deadline_risk": "Project deadline risk",
    "quality_threshold": "Below quality threshold",
}


def readiness_status(readiness: float, qa_pass_rate: float, days_to_deadline: int) -> str:
    if readiness >= 92 and qa_pass_rate >= 88:
        return "ready"
    if days_to_deadline <= 5 and readiness < 75:
        return "critical"
    if readiness < 60 or qa_pass_rate < 72:
        return "at_risk"
    return "watch"


def risk_level(readiness: float, open_flags: int, days_to_deadline: int) -> str:
    if days_to_deadline < 0 or (days_to_deadline <= 4 and readiness < 80) or open_flags > 55:
        return "critical"
    if days_to_deadline <= 10 or readiness < 70 or open_flags > 25:
        return "high"
    if readiness < 88 or open_flags > 8:
        return "medium"
    return "low"


def short_comment(comment: str) -> bool:
    cleaned = " ".join(comment.strip().split())
    return len(cleaned) < 18 or cleaned.lower() in {"ok", "fine", "good", "looks good"}


def compute_project_rollup(db: Session, project: Project, now: datetime) -> dict:
    rows = db.execute(
        select(EvaluationTask.status, func.count(EvaluationTask.id))
        .where(EvaluationTask.project_id == project.id)
        .group_by(EvaluationTask.status)
    ).all()
    status_counts = {status: count for status, count in rows}
    approved = status_counts.get("approved", 0) + status_counts.get("delivered", 0)
    total = sum(status_counts.values()) or project.target_dataset_size
    readiness = round((approved / max(project.target_dataset_size, 1)) * 100, 1)
    reviewed = (
        status_counts.get("approved", 0)
        + status_counts.get("delivered", 0)
        + status_counts.get("rejected", 0)
    )
    rejected = status_counts.get("rejected", 0)
    qa_pass_rate = round(((reviewed - rejected) / reviewed) * 100, 1) if reviewed else 0
    open_flags = db.scalar(
        select(func.count(QualityFlag.id)).where(
            QualityFlag.project_id == project.id,
            QualityFlag.status.in_(("open", "triaged")),
        )
    ) or 0
    days = (project.deadline - now).days
    return {
        "task_counts": status_counts,
        "total_tasks": total,
        "approved_tasks": approved,
        "readiness_score": min(readiness, 100),
        "qa_pass_rate": qa_pass_rate,
        "open_flags": open_flags,
        "days_to_deadline": days,
        "risk_level": risk_level(readiness, open_flags, days),
        "readiness_status": readiness_status(readiness, qa_pass_rate, days),
    }


def category_counts(flags: Iterable[QualityFlag]) -> list[dict]:
    counts = Counter(flag.category for flag in flags)
    return [
        {"category": CATEGORY_LABELS.get(category, category), "count": count}
        for category, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


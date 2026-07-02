from __future__ import annotations

import hashlib
import io
import json
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .database import get_db
from .models import (
    Contributor,
    EvaluationTask,
    ExportRecord,
    HumanRating,
    ModelResponse,
    Project,
    QAReview,
    QualityFlag,
    RubricScore,
)
from .quality import CATEGORY_LABELS, category_counts, compute_project_rollup
from .schemas import DeliveryNotesRequest, RubricDraftRequest
from .seed import BASE_NOW, STATUSES, ensure_seed_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_seed_data()
    yield


app = FastAPI(
    title="HumanLoop Command Center API",
    version="1.0.0",
    description="Synthetic AI data operations platform for expert-labeled LLM evaluation pipelines.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def final_rating(task: EvaluationTask) -> HumanRating | None:
    ratings = sorted(task.human_ratings, key=lambda row: row.created_at)
    for rating in reversed(ratings):
        if rating.is_final:
            return rating
    return ratings[-1] if ratings else None


def project_payload(db: Session, project: Project, now: datetime) -> dict:
    rollup = compute_project_rollup(db, project, now)
    return {
        "id": project.id,
        "name": project.name,
        "customer": project.customer.name,
        "domain": project.domain,
        "task_type": project.task_type,
        "target_dataset_size": project.target_dataset_size,
        "deadline": iso(project.deadline),
        "quality_threshold": project.quality_threshold,
        "required_expertise": project.required_expertise,
        "priority": project.priority,
        "delivery_format": project.delivery_format,
        "status": project.status,
        **rollup,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "humanloop-command-center"}


@app.get("/api/projects")
def get_projects(
    domain: str | None = None,
    risk: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    now = BASE_NOW
    query = db.query(Project).options(joinedload(Project.customer)).order_by(Project.deadline.asc())
    if domain and domain != "all":
        query = query.filter(Project.domain == domain)
    projects = [project_payload(db, project, now) for project in query.all()]
    if risk and risk != "all":
        projects = [project for project in projects if project["risk_level"] == risk]
    return projects


@app.get("/api/contributors")
def get_contributors(
    domain: str | None = None,
    coaching: bool | None = None,
    sort: str = "quality",
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(Contributor)
    if domain and domain != "all":
        query = query.filter(Contributor.domain_expertise.contains(domain))
    if coaching is not None:
        query = query.filter(Contributor.coaching_flag == coaching)
    contributors = query.all()
    flag_counts = dict(
        db.execute(
            select(QualityFlag.contributor_id, func.count(QualityFlag.id))
            .where(QualityFlag.contributor_id.is_not(None))
            .group_by(QualityFlag.contributor_id)
        ).all()
    )
    rows = [
        {
            "id": contributor.id,
            "name": contributor.name,
            "domain_expertise": contributor.domain_expertise,
            "location_tz": contributor.location_tz,
            "capacity_per_week": contributor.capacity_per_week,
            "current_assignment_status": contributor.current_assignment_status,
            "approval_rate": round(contributor.approval_rate * 100, 1),
            "average_rubric_score": contributor.average_rubric_score,
            "rejection_rate": round(contributor.rejection_rate * 100, 1),
            "training_status": contributor.training_status,
            "coaching_flag": contributor.coaching_flag,
            "historical_throughput": contributor.historical_throughput,
            "active_tasks": contributor.active_tasks,
            "load_percent": round((contributor.active_tasks / max(contributor.capacity_per_week, 1)) * 100, 1),
            "open_flags": flag_counts.get(contributor.id, 0),
        }
        for contributor in contributors
    ]
    if sort == "rejection":
        rows.sort(key=lambda row: row["rejection_rate"], reverse=True)
    elif sort == "load":
        rows.sort(key=lambda row: row["load_percent"], reverse=True)
    elif sort == "throughput":
        rows.sort(key=lambda row: row["historical_throughput"], reverse=True)
    else:
        rows.sort(key=lambda row: (row["average_rubric_score"], row["approval_rate"]), reverse=True)
    return rows


@app.get("/api/tasks")
def get_tasks(
    domain: str | None = None,
    status: str | None = None,
    flagged: bool | None = None,
    contributor: str | None = None,
    search: str | None = None,
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = (
        db.query(EvaluationTask)
        .options(
            joinedload(EvaluationTask.project).joinedload(Project.customer),
            joinedload(EvaluationTask.assigned_contributor),
            joinedload(EvaluationTask.model_response),
            joinedload(EvaluationTask.human_ratings),
            joinedload(EvaluationTask.rubric_score),
            joinedload(EvaluationTask.qa_review),
        )
        .join(Project)
    )
    if domain and domain != "all":
        query = query.filter(Project.domain == domain)
    if status and status != "all":
        query = query.filter(EvaluationTask.status == status)
    if flagged is not None:
        query = query.filter(EvaluationTask.qa_flag_count > 0 if flagged else EvaluationTask.qa_flag_count == 0)
    if contributor:
        query = query.filter(EvaluationTask.assigned_contributor_id == contributor)
    if search:
        like = f"%{search}%"
        query = query.filter(EvaluationTask.prompt.ilike(like))
    tasks = query.order_by(EvaluationTask.created_at.desc()).limit(limit).all()
    rows = []
    for task in tasks:
        rating = final_rating(task)
        rows.append(
            {
                "id": task.id,
                "project_id": task.project_id,
                "project_name": task.project.name,
                "customer": task.project.customer.name,
                "domain": task.project.domain,
                "prompt": task.prompt,
                "model_response": task.model_response.response if task.model_response else "",
                "human_rating": rating.rating if rating else None,
                "rubric_score": task.rubric_score.overall_score if task.rubric_score else None,
                "reviewer_comments": rating.reviewer_comments if rating else "",
                "qa_status": task.qa_review.qa_status if task.qa_review else "not reviewed",
                "reviewer": task.reviewer or "unassigned",
                "assigned_contributor": task.assigned_contributor.name if task.assigned_contributor else "unassigned",
                "assigned_contributor_id": task.assigned_contributor_id,
                "status": task.status,
                "qa_flag_count": task.qa_flag_count,
                "submission_time": iso(task.submission_time),
                "risk_score": task.risk_score,
            }
        )
    return rows


@app.get("/api/quality-flags")
def get_quality_flags(
    category: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    limit: int = Query(default=500, ge=1, le=1500),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = (
        db.query(QualityFlag)
        .options(
            joinedload(QualityFlag.project),
            joinedload(QualityFlag.contributor),
            joinedload(QualityFlag.task),
        )
        .order_by(QualityFlag.created_at.desc())
    )
    if category and category != "all":
        query = query.filter(QualityFlag.category == category)
    if severity and severity != "all":
        query = query.filter(QualityFlag.severity == severity)
    if status and status != "all":
        query = query.filter(QualityFlag.status == status)
    return [
        {
            "id": flag.id,
            "task_id": flag.task_id,
            "project_id": flag.project_id,
            "project_name": flag.project.name if flag.project else "network-wide",
            "contributor_id": flag.contributor_id,
            "contributor_name": flag.contributor.name if flag.contributor else "n/a",
            "category": flag.category,
            "category_label": CATEGORY_LABELS.get(flag.category, flag.category),
            "severity": flag.severity,
            "owner": flag.owner,
            "status": flag.status,
            "description": flag.description,
            "created_at": iso(flag.created_at),
        }
        for flag in query.limit(limit).all()
    ]


@app.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    now = BASE_NOW
    projects = db.query(Project).options(joinedload(Project.customer)).all()
    project_rows = [project_payload(db, project, now) for project in projects]
    status_counts = dict(
        db.execute(
            select(EvaluationTask.status, func.count(EvaluationTask.id)).group_by(EvaluationTask.status)
        ).all()
    )
    qa_rows = db.execute(select(QAReview.qa_status, func.count(QAReview.id)).group_by(QAReview.qa_status)).all()
    qa_counts = {status: count for status, count in qa_rows}
    reviewed = sum(qa_counts.values())
    qa_pass_rate = round((qa_counts.get("pass", 0) / reviewed) * 100, 1) if reviewed else 0
    contributor_approval = db.scalar(select(func.avg(Contributor.approval_rate))) or 0
    active_projects = sum(1 for project in projects if project.status in {"active", "in QA", "delivery prep", "intake"})
    readiness = round(sum(row["readiness_score"] for row in project_rows) / max(len(project_rows), 1), 1)
    review_backlog = status_counts.get("submitted", 0) + status_counts.get("in review", 0)
    sla_risk = sum(1 for row in project_rows if row["risk_level"] in {"high", "critical"})
    delivered_ready = sum(1 for row in project_rows if row["readiness_status"] == "ready")
    completed_today = db.scalar(
        select(func.count(EvaluationTask.id)).where(
            EvaluationTask.status.in_(("approved", "delivered")),
            EvaluationTask.submission_time >= now - timedelta(days=1),
        )
    ) or 0

    domains = sorted({project.domain for project in projects})
    domain_workload: list[dict] = []
    for domain in domains:
        domain_tasks = db.scalar(
            select(func.count(EvaluationTask.id)).join(Project).where(Project.domain == domain)
        ) or 0
        domain_flags = db.scalar(
            select(func.count(QualityFlag.id)).join(Project, QualityFlag.project_id == Project.id).where(Project.domain == domain)
        ) or 0
        domain_approved = db.scalar(
            select(func.count(EvaluationTask.id))
            .join(Project)
            .where(Project.domain == domain, EvaluationTask.status.in_(("approved", "delivered")))
        ) or 0
        domain_workload.append(
            {
                "domain": domain,
                "tasks": domain_tasks,
                "approved": domain_approved,
                "open_flags": domain_flags,
                "readiness": round((domain_approved / max(domain_tasks, 1)) * 100, 1),
            }
        )

    qa_by_domain = []
    for domain in domains:
        rows = db.execute(
            select(QAReview.qa_status, func.count(QAReview.id))
            .join(EvaluationTask)
            .join(Project)
            .where(Project.domain == domain)
            .group_by(QAReview.qa_status)
        ).all()
        counts = {status: count for status, count in rows}
        total = sum(counts.values())
        qa_by_domain.append(
            {
                "domain": domain,
                "passRate": round((counts.get("pass", 0) / total) * 100, 1) if total else 0,
                "reviewed": total,
            }
        )

    contributors = db.query(Contributor).all()
    quality_bins = Counter()
    for contributor in contributors:
        if contributor.average_rubric_score >= 4.5:
            quality_bins["4.5-5.0"] += 1
        elif contributor.average_rubric_score >= 4.0:
            quality_bins["4.0-4.49"] += 1
        elif contributor.average_rubric_score >= 3.5:
            quality_bins["3.5-3.99"] += 1
        elif contributor.average_rubric_score >= 3.0:
            quality_bins["3.0-3.49"] += 1
        else:
            quality_bins["<3.0"] += 1
    contributor_quality_distribution = [
        {"band": band, "contributors": quality_bins.get(band, 0)}
        for band in ["<3.0", "3.0-3.49", "3.5-3.99", "4.0-4.49", "4.5-5.0"]
    ]

    throughput_map = {
        (now - timedelta(days=day)).date().isoformat(): 0
        for day in range(13, -1, -1)
    }
    throughput_rows = db.execute(
        select(func.date(EvaluationTask.submission_time), func.count(EvaluationTask.id))
        .where(
            EvaluationTask.submission_time.is_not(None),
            EvaluationTask.submission_time >= now - timedelta(days=13),
            EvaluationTask.status.in_(("approved", "delivered")),
        )
        .group_by(func.date(EvaluationTask.submission_time))
    ).all()
    for date_key, count in throughput_rows:
        throughput_map[str(date_key)] = count
    throughput = [{"date": date_key, "tasks": count} for date_key, count in throughput_map.items()]

    rejection_reasons = [
        {"reason": reason or "Other", "count": count}
        for reason, count in db.execute(
            select(QAReview.rejection_reason, func.count(QAReview.id))
            .where(QAReview.rejection_reason.is_not(None))
            .group_by(QAReview.rejection_reason)
            .order_by(func.count(QAReview.id).desc())
        ).all()
    ]

    flags = db.query(QualityFlag).all()
    leaderboard = sorted(
        [
            {
                "id": contributor.id,
                "name": contributor.name,
                "domain_expertise": contributor.domain_expertise,
                "approval_rate": round(contributor.approval_rate * 100, 1),
                "average_rubric_score": contributor.average_rubric_score,
                "rejection_rate": round(contributor.rejection_rate * 100, 1),
                "coaching_flag": contributor.coaching_flag,
                "active_tasks": contributor.active_tasks,
                "capacity_per_week": contributor.capacity_per_week,
            }
            for contributor in contributors
        ],
        key=lambda row: (row["average_rubric_score"], row["approval_rate"]),
        reverse=True,
    )
    low_performers = sorted(
        [row for row in leaderboard if row["coaching_flag"] or row["average_rubric_score"] < 3.5],
        key=lambda row: (row["average_rubric_score"], -row["rejection_rate"]),
    )[:8]
    overloaded = sorted(
        [row for row in leaderboard if row["active_tasks"] > row["capacity_per_week"]],
        key=lambda row: row["active_tasks"] / max(row["capacity_per_week"], 1),
        reverse=True,
    )[:8]
    coverage_gaps = []
    for domain in domains:
        available = sum(
            1
            for contributor in contributors
            if domain in contributor.domain_expertise
            and contributor.current_assignment_status in {"available", "assigned"}
            and contributor.approval_rate >= 0.82
        )
        load = next(item for item in domain_workload if item["domain"] == domain)["tasks"]
        coverage_gaps.append(
            {
                "domain": domain,
                "qualified_contributors": available,
                "tasks_per_contributor": round(load / max(available, 1), 1),
                "status": "gap" if available < 35 else "covered",
            }
        )

    return {
        "generated_at": iso(now),
        "kpis": {
            "active_projects": active_projects,
            "tasks_completed_today": completed_today,
            "dataset_readiness_score": readiness,
            "qa_pass_rate": qa_pass_rate,
            "review_backlog": review_backlog,
            "sla_risk": sla_risk,
            "contributor_approval_rate": round(contributor_approval * 100, 1),
            "rejected_task_count": status_counts.get("rejected", 0),
            "customer_delivery_readiness": round((delivered_ready / max(len(project_rows), 1)) * 100, 1),
        },
        "pipeline_funnel": [{"status": status, "count": status_counts.get(status, 0)} for status in STATUSES],
        "qa_pass_rate_by_domain": qa_by_domain,
        "contributor_quality_distribution": contributor_quality_distribution,
        "project_deadline_risk": sorted(project_rows, key=lambda row: (row["days_to_deadline"], -row["open_flags"]))[:10],
        "task_throughput_over_time": throughput,
        "rejection_reasons": rejection_reasons,
        "domain_workload": domain_workload,
        "quality_flag_categories": category_counts(flags),
        "contributor_leaderboard": leaderboard[:10],
        "low_performing_contributors": low_performers,
        "overloaded_contributors": overloaded,
        "domain_coverage_gaps": coverage_gaps,
        "top_risk_projects": sorted(
            project_rows,
            key=lambda row: ({"critical": 3, "high": 2, "medium": 1, "low": 0}[row["risk_level"]], -row["open_flags"]),
            reverse=True,
        )[:10],
    }


@app.get("/api/projects/{project_id}/export")
def export_project(
    project_id: int,
    format: Literal["jsonl", "csv"] = "jsonl",
    db: Session = Depends(get_db),
) -> StreamingResponse:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tasks = (
        db.query(EvaluationTask)
        .options(
            joinedload(EvaluationTask.project),
            joinedload(EvaluationTask.model_response),
            joinedload(EvaluationTask.human_ratings),
            joinedload(EvaluationTask.rubric_score),
            joinedload(EvaluationTask.qa_review),
        )
        .where(EvaluationTask.project_id == project_id, EvaluationTask.status.in_(("approved", "delivered")))
        .order_by(EvaluationTask.id.asc())
        .all()
    )
    rows = []
    for task in tasks:
        rating = final_rating(task)
        if not rating or rating.rating is None:
            continue
        rows.append(
            {
                "prompt": task.prompt,
                "model_response": task.model_response.response if task.model_response else "",
                "final_human_rating": rating.rating,
                "rubric_score": task.rubric_score.overall_score if task.rubric_score else None,
                "qa_status": task.qa_review.qa_status if task.qa_review else "not reviewed",
                "reviewer_notes": task.qa_review.notes if task.qa_review else rating.reviewer_comments,
                "domain": project.domain,
                "project_id": project.id,
            }
        )
    if format == "csv":
        content = pd.DataFrame(rows).to_csv(index=False)
        media_type = "text/csv"
        extension = "csv"
    else:
        content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        media_type = "application/x-ndjson"
        extension = "jsonl"
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()[:20]
    db.add(
        ExportRecord(
            project_id=project_id,
            format=format.upper(),
            row_count=len(rows),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            checksum=checksum,
        )
    )
    db.commit()
    filename = f"humanloop_project_{project_id}_{checksum}.{extension}"
    return StreamingResponse(
        io.StringIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/llm/rubric")
def generate_rubric(request: RubricDraftRequest) -> dict:
    base_weights = {
        "factuality evaluation": [0.38, 0.22, 0.16, 0.24],
        "safety review": [0.24, 0.18, 0.40, 0.18],
        "coding review": [0.30, 0.20, 0.12, 0.38],
        "preference ranking": [0.24, 0.30, 0.16, 0.30],
        "rubric scoring": [0.28, 0.26, 0.18, 0.28],
    }
    weights = base_weights.get(request.task_type, [0.30, 0.25, 0.20, 0.25])
    criteria = [
        ("Accuracy", weights[0], f"Validate {request.domain} facts against the customer source packet."),
        ("Completeness", weights[1], "Check whether the response answers every requested part of the prompt."),
        ("Safety and Policy", weights[2], "Flag unsafe, misleading, or policy-violating statements."),
        ("Reasoning Quality", weights[3], "Assess chain-of-thought quality through concise reviewer rationale, not hidden reasoning."),
    ]
    return {
        "mode": "deterministic_mock",
        "customer_name": request.customer_name,
        "rubric_title": f"{request.domain.title()} {request.task_type.title()} Rubric",
        "quality_threshold": request.quality_threshold,
        "target_dataset_size": request.target_dataset_size,
        "criteria": [
            {"name": name, "weight": weight, "guidance": guidance}
            for name, weight, guidance in criteria
        ],
        "calibration_notes": [
            f"Require {request.required_expertise} for primary labels.",
            "Escalate examples with score spread above 1.25 points to QA review.",
            "Reject labels with missing ratings, low-effort comments, or unsupported claims.",
        ],
    }


@app.post("/api/llm/delivery-notes")
def generate_delivery_notes(request: DeliveryNotesRequest, db: Session = Depends(get_db)) -> dict:
    project = db.query(Project).options(joinedload(Project.customer)).where(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    rollup = compute_project_rollup(db, project, BASE_NOW)
    flags = (
        db.query(QualityFlag)
        .where(QualityFlag.project_id == project.id, QualityFlag.status.in_(("open", "triaged")))
        .order_by(QualityFlag.severity.desc())
        .limit(5)
        .all()
    )
    blockers = [CATEGORY_LABELS.get(flag.category, flag.category) for flag in flags]
    note = (
        f"{project.customer.name} delivery packet for {project.name}: "
        f"{rollup['approved_tasks']} approved tasks are ready against a target of {project.target_dataset_size}. "
        f"Dataset readiness is {rollup['readiness_score']}% with QA pass rate {rollup['qa_pass_rate']}%. "
        f"Risk level is {rollup['risk_level']} with {rollup['open_flags']} open or triaged quality flags."
    )
    if blockers:
        note += " Primary follow-ups: " + ", ".join(blockers[:3]) + "."
    return {
        "mode": "deterministic_mock",
        "project_id": project.id,
        "audience": request.audience,
        "delivery_note": note,
        "recommended_actions": [
            "Close high-severity QA flags before final handoff.",
            "Re-run duplicate prompt validation on the export candidate set.",
            "Include rubric calibration summary in customer-facing delivery notes.",
        ],
    }


@app.get("/api/llm/contributor-issues")
def contributor_issue_summary(db: Session = Depends(get_db)) -> dict:
    contributors = get_contributors(coaching=True, sort="rejection", db=db)[:12]
    themes = [
        "Prioritize recalibration for contributors with high rejection rates and low rubric scores.",
        "Move overloaded experts out of urgent queues before assigning new deadline-sensitive work.",
        "Pair calibrating contributors with reviewers from the same domain for the next two batches.",
    ]
    return {"mode": "deterministic_mock", "themes": themes, "contributors": contributors}

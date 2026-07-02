from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import (
    ActivityLog,
    Contributor,
    ContributorTraining,
    Customer,
    EvaluationTask,
    ExportRecord,
    HumanRating,
    ModelResponse,
    Project,
    QAReview,
    QualityFlag,
    RubricScore,
)


SEED = 20260702
BASE_NOW = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc).replace(tzinfo=None)
DOMAINS = ["finance", "healthcare", "legal", "coding", "STEM", "general reasoning"]
TASK_TYPES = [
    "preference ranking",
    "factuality evaluation",
    "rubric scoring",
    "safety review",
    "coding review",
]
PRIORITIES = ["standard", "high", "urgent"]
FORMATS = ["JSONL", "CSV"]
STATUSES = ["unassigned", "assigned", "submitted", "in review", "approved", "rejected", "delivered"]
REJECTION_REASONS = [
    "Missing evidence citation",
    "Rubric mismatch",
    "Low-effort rationale",
    "Safety policy miss",
    "Incorrect factual judgment",
    "Formatting issue",
]
TIMEZONES = [
    "US/Pacific",
    "US/Mountain",
    "US/Central",
    "US/Eastern",
    "Europe/London",
    "Europe/Berlin",
    "Asia/Kolkata",
    "Asia/Singapore",
]
FIRST_NAMES = [
    "Aarav",
    "Maya",
    "Jordan",
    "Sofia",
    "Ethan",
    "Priya",
    "Noah",
    "Anika",
    "Liam",
    "Iris",
    "Mateo",
    "Nora",
    "Arjun",
    "Leah",
    "Owen",
    "Zara",
    "Chen",
    "Mina",
    "Ravi",
    "Elena",
]
LAST_NAMES = [
    "Kapoor",
    "Shah",
    "Bennett",
    "Morgan",
    "Patel",
    "Nguyen",
    "Rao",
    "Chen",
    "Williams",
    "Singh",
    "Garcia",
    "Khan",
    "Mehta",
    "Carter",
    "Iyer",
    "Lopez",
]
CUSTOMER_NAMES = [
    "Aster Frontier Labs",
    "Northstar AI",
    "Veridian Research",
    "Cascade Model Systems",
    "Helio Alignment",
    "Atlas EvalWorks",
    "Mosaic Intelligence",
    "Cobalt Safety Lab",
    "Redwood Frontier AI",
    "Quantis Model Lab",
    "Meridian Benchmarks",
    "Keystone AI",
    "Lattice Cognition",
    "Apex Reasoning",
    "Valkyrie ML",
    "Nimbus Eval Studio",
    "SignalForge AI",
    "Brightline Models",
    "Strata Alignment",
    "Orion Data Foundry",
    "BluePeak Research",
    "ForgeMind Labs",
    "Pinnacle Eval Cloud",
    "Kite AI Systems",
]


def reset_database(db: Session) -> None:
    for model in [
        ActivityLog,
        ExportRecord,
        QualityFlag,
        QAReview,
        RubricScore,
        HumanRating,
        ModelResponse,
        EvaluationTask,
        ContributorTraining,
        Contributor,
        Project,
        Customer,
    ]:
        db.execute(delete(model))
    db.commit()


def project_targets(rng: random.Random) -> list[int]:
    targets = [300 for _ in range(40)]
    for _ in range(90):
        source = rng.randrange(40)
        sink = rng.randrange(40)
        if source == sink:
            continue
        delta = rng.choice([8, 10, 12, 15])
        if targets[source] - delta >= 230 and targets[sink] + delta <= 390:
            targets[source] -= delta
            targets[sink] += delta
    assert sum(targets) == 12000
    return targets


def bounded_score(value: float) -> float:
    return round(max(1.0, min(5.0, value)), 2)


def make_prompt(domain: str, task_type: str, n: int) -> str:
    topic_map = {
        "finance": ["credit exposure", "portfolio stress", "earnings guidance", "fraud escalation"],
        "healthcare": ["clinical guideline", "patient discharge", "adverse event", "medical coding"],
        "legal": ["contract clause", "discovery request", "compliance memo", "case precedent"],
        "coding": ["Python function", "SQL query", "API review", "test failure"],
        "STEM": ["physics derivation", "biology explanation", "statistics proof", "engineering tradeoff"],
        "general reasoning": ["planning scenario", "logic puzzle", "policy comparison", "multi-step answer"],
    }
    topic = topic_map[domain][n % len(topic_map[domain])]
    return (
        f"Evaluate the model response for a {domain} {task_type} task about {topic}. "
        f"Apply the customer rubric and identify any factual, safety, or reasoning issues. Case #{n:05d}."
    )


def make_response(domain: str, n: int) -> str:
    style = [
        "The response is mostly complete but relies on one unsupported assumption.",
        "The answer provides a structured explanation and cites the core evidence.",
        "The model misses a domain-specific constraint that an expert reviewer should catch.",
        "The response is concise and operationally useful, though the rationale needs tightening.",
    ][n % 4]
    return f"{style} Domain context: {domain}. Synthetic response version {n % 17}."


def rating_comment(score: float, rng: random.Random, low_effort: bool = False) -> str:
    if low_effort:
        return rng.choice(["ok", "fine", "looks good", "needs work"])
    if score >= 4.4:
        return "Strong rationale, clear evidence alignment, and no material rubric violations."
    if score >= 3.6:
        return "Acceptable judgment with minor rubric ambiguity that QA should monitor."
    if score >= 2.8:
        return "Partial alignment; reviewer noted missing evidence and inconsistent reasoning."
    return "Reviewer identified major rubric misses and recommends rejection or relabeling."


def ensure_seed_data(force: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        projects = db.scalar(select(func.count(Project.id))) or 0
        tasks = db.scalar(select(func.count(EvaluationTask.id))) or 0
        ratings = db.scalar(select(func.count(HumanRating.id))) or 0
        if not force and projects >= 40 and tasks >= 12000 and ratings >= 25000:
            return
        seed_database(db)


def seed_database(db: Session) -> None:
    rng = random.Random(SEED)
    reset_database(db)

    customers: list[Customer] = []
    for idx, name in enumerate(CUSTOMER_NAMES, start=1):
        customers.append(
            Customer(
                name=name,
                segment=rng.choice(["frontier lab", "enterprise AI", "alignment research", "benchmark vendor"]),
                contact_email=f"ops{idx}@{name.lower().replace(' ', '').replace('-', '')}.example",
                created_at=BASE_NOW - timedelta(days=55 + idx),
            )
        )
    db.add_all(customers)
    db.commit()

    targets = project_targets(rng)
    projects: list[Project] = []
    for idx in range(40):
        domain = DOMAINS[idx % len(DOMAINS)]
        task_type = TASK_TYPES[(idx + rng.randrange(len(TASK_TYPES))) % len(TASK_TYPES)]
        priority = rng.choices(PRIORITIES, weights=[0.55, 0.32, 0.13], k=1)[0]
        deadline_window = rng.randint(-5, 42)
        if priority == "urgent":
            deadline_window = rng.randint(2, 18)
        projects.append(
            Project(
                customer_id=customers[idx % len(customers)].id,
                name=f"{domain.title()} {task_type.title()} Batch {idx + 1:02d}",
                domain=domain,
                task_type=task_type,
                target_dataset_size=targets[idx],
                deadline=BASE_NOW + timedelta(days=deadline_window),
                quality_threshold=round(rng.uniform(3.85, 4.55), 2),
                required_expertise=rng.choice(
                    [
                        f"senior {domain} specialist",
                        f"{domain} SME with QA calibration",
                        f"expert reviewer for {task_type}",
                    ]
                ),
                priority=priority,
                delivery_format=FORMATS[idx % 2],
                status=rng.choices(["active", "in QA", "delivery prep", "intake"], [0.52, 0.22, 0.18, 0.08])[0],
                created_at=BASE_NOW - timedelta(days=rng.randint(8, 50)),
            )
        )
    db.add_all(projects)
    db.commit()

    contributors: list[dict] = []
    training_rows: list[dict] = []
    high_rejection_contributors: list[str] = []
    for idx in range(300):
        cid = f"EXP-{idx + 1:04d}"
        primary = DOMAINS[idx % len(DOMAINS)]
        secondary = rng.sample([d for d in DOMAINS if d != primary], k=rng.choice([1, 1, 2]))
        expertise = ", ".join([primary, *secondary])
        quality_band = rng.random()
        approval = round(rng.uniform(0.88, 0.985) if quality_band > 0.18 else rng.uniform(0.66, 0.84), 3)
        rejection = round(max(0.01, min(0.29, 1 - approval + rng.uniform(-0.015, 0.035))), 3)
        avg_score = round(rng.uniform(4.15, 4.92) if approval > 0.87 else rng.uniform(2.75, 3.85), 2)
        coaching = approval < 0.78 or avg_score < 3.35 or rejection > 0.18
        if rejection > 0.18:
            high_rejection_contributors.append(cid)
        contributors.append(
            {
                "id": cid,
                "name": f"{FIRST_NAMES[idx % len(FIRST_NAMES)]} {LAST_NAMES[(idx * 3) % len(LAST_NAMES)]}",
                "domain_expertise": expertise,
                "location_tz": TIMEZONES[idx % len(TIMEZONES)],
                "capacity_per_week": rng.randint(14, 60),
                "current_assignment_status": rng.choices(
                    ["available", "assigned", "overloaded", "paused"], [0.28, 0.52, 0.14, 0.06]
                )[0],
                "approval_rate": approval,
                "average_rubric_score": avg_score,
                "rejection_rate": rejection,
                "training_status": rng.choices(["certified", "calibrating", "needs refresh"], [0.62, 0.27, 0.11])[0],
                "coaching_flag": coaching,
                "historical_throughput": rng.randint(140, 1800),
                "active_tasks": 0,
            }
        )
        training_rows.append(
            {
                "contributor_id": cid,
                "module_name": f"{primary.title()} Rubric Calibration",
                "status": "complete" if not coaching else rng.choice(["in progress", "assigned"]),
                "completed_at": BASE_NOW - timedelta(days=rng.randint(1, 70)) if not coaching else None,
            }
        )
    db.bulk_insert_mappings(Contributor, contributors)
    db.bulk_insert_mappings(ContributorTraining, training_rows)
    db.commit()

    contributors_by_domain = defaultdict(list)
    for row in contributors:
        for domain in DOMAINS:
            if domain in row["domain_expertise"]:
                contributors_by_domain[domain].append(row)

    task_rows: list[dict] = []
    response_rows: list[dict] = []
    rating_rows: list[dict] = []
    rubric_rows: list[dict] = []
    qa_rows: list[dict] = []
    flag_rows: list[dict] = []
    activity_rows: list[dict] = []
    active_counts: Counter[str] = Counter()
    task_index = 0
    rating_count = 0

    project_status_weights = {
        "intake": [0.25, 0.32, 0.18, 0.12, 0.08, 0.03, 0.02],
        "active": [0.08, 0.18, 0.18, 0.16, 0.27, 0.07, 0.06],
        "in QA": [0.02, 0.08, 0.16, 0.24, 0.36, 0.09, 0.05],
        "delivery prep": [0.01, 0.03, 0.08, 0.12, 0.36, 0.05, 0.35],
    }

    for project in projects:
        domain_contributors = contributors_by_domain[project.domain]
        weights = project_status_weights[project.status]
        for local_idx in range(project.target_dataset_size):
            task_index += 1
            task_id = f"TASK-{task_index:06d}"
            status = rng.choices(STATUSES, weights=weights, k=1)[0]
            contributor = rng.choice(domain_contributors) if status != "unassigned" else None
            assigned_id = contributor["id"] if contributor else None
            if assigned_id and status in {"assigned", "submitted", "in review"}:
                active_counts[assigned_id] += 1
            reviewer = rng.choice(["QA Lead Mina", "QA Lead Ravi", "Reviewer Ops Chen", "Reviewer Ops Sofia"])
            duplicate_prompt = task_index % 257 == 0
            prompt = make_prompt(project.domain, project.task_type, task_index - 1 if duplicate_prompt else task_index)
            submission_time = None
            if status in {"submitted", "in review", "approved", "rejected", "delivered"}:
                submission_time = BASE_NOW - timedelta(days=rng.randint(0, 21), hours=rng.randint(0, 21))
            risk = rng.random()
            flag_count = 0

            low_effort = task_index % 71 == 0
            missing_rating = task_index % 113 == 0
            inconsistent = task_index % 89 == 0
            fast_submission = task_index % 47 == 0 and status not in {"unassigned", "assigned"}
            base_score = bounded_score(rng.gauss(4.1, 0.55))
            if status == "rejected":
                base_score = bounded_score(rng.gauss(2.65, 0.45))
            if inconsistent:
                base_score = bounded_score(rng.choice([2.4, 4.8]))

            flag_specs: list[tuple[str, str, str, str]] = []
            if duplicate_prompt:
                flag_specs.append(("duplicate_prompt", "medium", "queue QA", "Prompt text matches another task in this project family."))
            if missing_rating:
                flag_specs.append(("missing_rating", "high", "review ops", "Final rating is missing or null after submission."))
            if inconsistent:
                flag_specs.append(("inconsistent_scoring", "high", "QA lead", "Reviewer scores diverge beyond allowed rubric variance."))
            if low_effort:
                flag_specs.append(("low_effort_comment", "medium", "contributor ops", "Reviewer comment is too short for customer auditability."))
            if fast_submission:
                flag_specs.append(("fast_submission", "medium", "trust ops", "Submission completed faster than expected for task complexity."))
            if status == "rejected" and rng.random() < 0.38:
                flag_specs.append(("quality_threshold", "high", "QA lead", "Rejected task sits below customer quality threshold."))

            flag_count = len(flag_specs)
            task_rows.append(
                {
                    "id": task_id,
                    "project_id": project.id,
                    "prompt": prompt,
                    "status": status,
                    "qa_flag_count": flag_count,
                    "assigned_contributor_id": assigned_id,
                    "reviewer": reviewer if status not in {"unassigned", "assigned"} else None,
                    "submission_time": submission_time,
                    "created_at": project.created_at + timedelta(hours=local_idx % 220),
                    "risk_score": round(risk, 3),
                }
            )
            response_rows.append(
                {
                    "task_id": task_id,
                    "model_name": rng.choice(["frontier-alpha", "frontier-beta", "reasoner-pro", "safety-large"]),
                    "response": make_response(project.domain, task_index),
                    "response_version": f"v{1 + (task_index % 4)}.{task_index % 9}",
                }
            )

            criteria = [bounded_score(base_score + rng.uniform(-0.35, 0.35)) for _ in range(4)]
            overall = bounded_score(sum(criteria) / 4)
            rubric_rows.append(
                {
                    "task_id": task_id,
                    "criteria_accuracy": criteria[0],
                    "criteria_completeness": criteria[1],
                    "criteria_safety": criteria[2],
                    "criteria_reasoning": criteria[3],
                    "overall_score": overall,
                    "consistency_check": not inconsistent,
                }
            )

            events_for_task = 3 if task_index <= 1000 else 2
            for event_idx in range(events_for_task):
                score_noise = rng.uniform(-0.45, 0.45)
                event_score = bounded_score(overall + score_noise)
                if inconsistent and event_idx == 0:
                    event_score = bounded_score(5.0 if overall < 3.5 else 2.0)
                is_final = event_idx == events_for_task - 1
                rating_rows.append(
                    {
                        "task_id": task_id,
                        "contributor_id": assigned_id or rng.choice(domain_contributors)["id"],
                        "rating": None if (missing_rating and is_final) else max(1, min(5, round(event_score))),
                        "rubric_score": event_score,
                        "reviewer_comments": rating_comment(event_score, rng, low_effort and is_final),
                        "review_event_type": "final" if is_final else rng.choice(["initial", "secondary_review"]),
                        "created_at": (submission_time or BASE_NOW) - timedelta(hours=events_for_task - event_idx),
                        "submission_seconds": rng.randint(22, 44) if fast_submission else rng.randint(95, 780),
                        "is_final": is_final,
                    }
                )
                rating_count += 1

            if status in {"submitted", "in review", "approved", "rejected", "delivered"}:
                qa_status = "pass"
                rejection_reason = None
                if status == "rejected":
                    qa_status = "fail"
                    rejection_reason = rng.choice(REJECTION_REASONS)
                elif flag_count >= 2 or overall < project.quality_threshold:
                    qa_status = rng.choice(["needs review", "pass"])
                qa_rows.append(
                    {
                        "task_id": task_id,
                        "reviewer": reviewer,
                        "qa_status": qa_status,
                        "notes": (
                            "Ready for delivery export."
                            if qa_status == "pass"
                            else "Requires rubric reconciliation before release."
                        ),
                        "reviewed_at": submission_time + timedelta(hours=rng.randint(1, 16)) if submission_time else None,
                        "rejection_reason": rejection_reason,
                    }
                )

            for category, severity, owner, description in flag_specs:
                flag_rows.append(
                    {
                        "task_id": task_id,
                        "project_id": project.id,
                        "contributor_id": assigned_id,
                        "category": category,
                        "severity": severity,
                        "owner": owner,
                        "status": rng.choices(["open", "triaged", "resolved"], [0.46, 0.34, 0.20])[0],
                        "description": description,
                        "created_at": submission_time or BASE_NOW - timedelta(days=rng.randint(0, 20)),
                    }
                )

        activity_rows.append(
            {
                "entity_type": "project",
                "entity_id": str(project.id),
                "action": "weekly calibration snapshot",
                "actor": "HumanLoop Ops Bot",
                "created_at": BASE_NOW - timedelta(days=rng.randint(0, 7)),
                "detail": f"{project.domain} project moved through {project.status} with target size {project.target_dataset_size}.",
            }
        )

    for row in contributors:
        row["active_tasks"] = active_counts[row["id"]]
        if row["id"] in high_rejection_contributors:
            flag_rows.append(
                {
                    "task_id": None,
                    "project_id": None,
                    "contributor_id": row["id"],
                    "category": "high_rejection_contributor",
                    "severity": "high" if row["rejection_rate"] > 0.22 else "medium",
                    "owner": "contributor ops",
                    "status": "open" if row["coaching_flag"] else "triaged",
                    "description": "Contributor rejection rate exceeds coaching threshold for recent batches.",
                    "created_at": BASE_NOW - timedelta(days=rng.randint(1, 14)),
                }
            )
        if row["coaching_flag"] and rng.random() < 0.48:
            flag_rows.append(
                {
                    "task_id": None,
                    "project_id": None,
                    "contributor_id": row["id"],
                    "category": "contributor_drift",
                    "severity": "medium",
                    "owner": "training ops",
                    "status": "triaged",
                    "description": "Recent reviewer calibration is drifting from historical rubric score.",
                    "created_at": BASE_NOW - timedelta(days=rng.randint(1, 14)),
                }
            )

    for project in projects:
        days_to_deadline = (project.deadline - BASE_NOW).days
        if days_to_deadline <= 8:
            flag_rows.append(
                {
                    "task_id": None,
                    "project_id": project.id,
                    "contributor_id": None,
                    "category": "deadline_risk",
                    "severity": "critical" if days_to_deadline <= 2 else "high",
                    "owner": "delivery ops",
                    "status": "open",
                    "description": "Project deadline is approaching before enough approved tasks are ready.",
                    "created_at": BASE_NOW - timedelta(hours=rng.randint(1, 72)),
                }
            )

    db.bulk_update_mappings(Contributor, contributors)
    db.bulk_insert_mappings(EvaluationTask, task_rows)
    db.bulk_insert_mappings(ModelResponse, response_rows)
    db.bulk_insert_mappings(RubricScore, rubric_rows)
    db.bulk_insert_mappings(HumanRating, rating_rows)
    db.bulk_insert_mappings(QAReview, qa_rows)
    db.bulk_insert_mappings(QualityFlag, flag_rows)
    db.bulk_insert_mappings(ActivityLog, activity_rows)
    db.commit()

    # Store a deterministic seed checksum in the activity stream for auditability.
    checksum_source = f"{len(projects)}:{len(task_rows)}:{rating_count}:{len(flag_rows)}:{SEED}"
    db.add(
        ActivityLog(
            entity_type="seed",
            entity_id="deterministic",
            action="seed completed",
            actor="seed.py",
            created_at=BASE_NOW,
            detail=f"Generated deterministic dataset checksum {hashlib.sha256(checksum_source.encode()).hexdigest()[:16]}.",
        )
    )
    db.commit()


if __name__ == "__main__":
    ensure_seed_data(force=True)
    print("Seeded HumanLoop Command Center data.")

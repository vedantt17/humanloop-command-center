from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    segment: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="customer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_dataset_size: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[str] = mapped_column(DateTime, nullable=False, index=True)
    quality_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    required_expertise: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    delivery_format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="projects")
    tasks: Mapped[list["EvaluationTask"]] = relationship(back_populates="project")
    flags: Mapped[list["QualityFlag"]] = relationship(back_populates="project")
    exports: Mapped[list["ExportRecord"]] = relationship(back_populates="project")


class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    domain_expertise: Mapped[str] = mapped_column(String(160), nullable=False)
    location_tz: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    current_assignment_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approval_rate: Mapped[float] = mapped_column(Float, nullable=False)
    average_rubric_score: Mapped[float] = mapped_column(Float, nullable=False)
    rejection_rate: Mapped[float] = mapped_column(Float, nullable=False)
    training_status: Mapped[str] = mapped_column(String(40), nullable=False)
    coaching_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    historical_throughput: Mapped[int] = mapped_column(Integer, nullable=False)
    active_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    training: Mapped[list["ContributorTraining"]] = relationship(back_populates="contributor")
    tasks: Mapped[list["EvaluationTask"]] = relationship(back_populates="assigned_contributor")
    flags: Mapped[list["QualityFlag"]] = relationship(back_populates="contributor")


class ContributorTraining(Base):
    __tablename__ = "contributor_training"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contributor_id: Mapped[str] = mapped_column(ForeignKey("contributors.id"), nullable=False)
    module_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)

    contributor: Mapped[Contributor] = relationship(back_populates="training")


class EvaluationTask(Base):
    __tablename__ = "evaluation_tasks"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    qa_flag_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_contributor_id: Mapped[str | None] = mapped_column(ForeignKey("contributors.id"), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    submission_time: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    project: Mapped[Project] = relationship(back_populates="tasks")
    assigned_contributor: Mapped[Contributor | None] = relationship(back_populates="tasks")
    model_response: Mapped["ModelResponse"] = relationship(back_populates="task", uselist=False)
    human_ratings: Mapped[list["HumanRating"]] = relationship(back_populates="task")
    rubric_score: Mapped["RubricScore"] = relationship(back_populates="task", uselist=False)
    qa_review: Mapped["QAReview"] = relationship(back_populates="task", uselist=False)
    flags: Mapped[list["QualityFlag"]] = relationship(back_populates="task")


class ModelResponse(Base):
    __tablename__ = "model_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("evaluation_tasks.id"), nullable=False, unique=True)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    response_version: Mapped[str] = mapped_column(String(40), nullable=False)

    task: Mapped[EvaluationTask] = relationship(back_populates="model_response")


class HumanRating(Base):
    __tablename__ = "human_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("evaluation_tasks.id"), nullable=False, index=True)
    contributor_id: Mapped[str] = mapped_column(ForeignKey("contributors.id"), nullable=False, index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rubric_score: Mapped[float] = mapped_column(Float, nullable=False)
    reviewer_comments: Mapped[str] = mapped_column(Text, nullable=False)
    review_event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    submission_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    task: Mapped[EvaluationTask] = relationship(back_populates="human_ratings")


class RubricScore(Base):
    __tablename__ = "rubric_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("evaluation_tasks.id"), nullable=False, unique=True)
    criteria_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_completeness: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_safety: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_reasoning: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    consistency_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    task: Mapped[EvaluationTask] = relationship(back_populates="rubric_score")


class QAReview(Base):
    __tablename__ = "qa_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("evaluation_tasks.id"), nullable=False, unique=True)
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    qa_status: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)

    task: Mapped[EvaluationTask] = relationship(back_populates="qa_review")


class QualityFlag(Base):
    __tablename__ = "quality_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_tasks.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    contributor_id: Mapped[str | None] = mapped_column(ForeignKey("contributors.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    owner: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)

    task: Mapped[EvaluationTask | None] = relationship(back_populates="flags")
    project: Mapped[Project | None] = relationship(back_populates="flags")
    contributor: Mapped[Contributor | None] = relationship(back_populates="flags")


class ExportRecord(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    checksum: Mapped[str] = mapped_column(String(80), nullable=False)

    project: Mapped[Project] = relationship(back_populates="exports")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)


from __future__ import annotations

from pydantic import BaseModel, Field


class RubricDraftRequest(BaseModel):
    customer_name: str = Field(default="Prospect AI Lab")
    domain: str
    task_type: str
    required_expertise: str
    quality_threshold: float = Field(default=4.2, ge=1, le=5)
    target_dataset_size: int = Field(default=500, ge=1)


class DeliveryNotesRequest(BaseModel):
    project_id: int
    audience: str = Field(default="customer operations lead")


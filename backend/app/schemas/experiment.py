from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field  # type: ignore

class ExperimentCreate(BaseModel):
    dataset_version_id: str = Field(..., min_length=1)
    agent_config_ids: List[str] = Field(..., min_length=1)
    split: str = Field("validation", max_length=32)
    repetitions: int = Field(default=1, ge=1, le=10)

    model_config = ConfigDict(extra="forbid")

class ScoreRead(BaseModel):
    id: str
    evaluator_name: str
    evaluator_version: str
    dimension: str
    applicable: bool
    status: str
    score: float
    reason_code: Optional[str] = None
    evidence: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)

class AttemptRead(BaseModel):
    id: str
    attempt_number: int
    environment_id: str
    status: str
    created_at: datetime
    scores: List[ScoreRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class RunRead(BaseModel):
    id: str
    experiment_id: str
    agent_config_id: str
    task_version_id: str
    repetition: int
    execution_status: str
    evaluation_status: str
    created_at: datetime
    updated_at: datetime
    attempts: List[AttemptRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class ExperimentRead(BaseModel):
    id: str
    workspace_id: str
    dataset_version_id: str
    status: str
    split: str
    repetitions: int
    config_ids: List[str]
    planned_runs: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExperimentCreateResponse(BaseModel):
    experiment_id: str
    status: str
    planned_runs: int

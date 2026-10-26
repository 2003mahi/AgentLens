from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field  # type: ignore

class TaskVersionBase(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=128)
    category: str = Field(..., min_length=1, max_length=64)
    difficulty: str = Field("medium", max_length=32)
    agent_input: Dict[str, Any] = Field(..., description="Agent visible user message and customer context")
    environment_fixture: Dict[str, Any] = Field(..., description="Hidden initial state fixtures")
    reviewer_behavior: Optional[Dict[str, Any]] = Field(default_factory=dict)
    evaluation: Dict[str, Any] = Field(..., description="Hidden evaluation criteria and invariants")

    model_config = ConfigDict(extra="forbid")

class TaskVersionRead(BaseModel):
    id: str
    task_id: str
    version: int
    category: str
    difficulty: str
    agent_input: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DatasetImportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    version_tag: str = Field("v1.0", min_length=1, max_length=64)
    split_manifest: Optional[Dict[str, List[str]]] = None
    tasks: List[TaskVersionBase] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")

class DatasetVersionRead(BaseModel):
    id: str
    dataset_id: str
    version_tag: str
    content_hash: str
    created_at: datetime
    tasks_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

class DatasetRead(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    versions: List[DatasetVersionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class DatasetImportResponse(BaseModel):
    dataset_id: str
    version_id: str
    version_tag: str
    tasks_imported: int
    content_hash: str

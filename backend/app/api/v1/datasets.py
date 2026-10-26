import hashlib
import json
from typing import List
from fastapi import APIRouter, Depends, status  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from backend.app.api.deps import AuthDep, DbDep
from backend.app.core.auth import AuthContext, verify_workspace_access
from backend.app.core.errors import NotFoundException, ConflictException
from backend.app.db.models import Dataset, DatasetVersion, TaskVersion, Workspace
from backend.app.schemas.dataset import (
    DatasetImportRequest,
    DatasetImportResponse,
    DatasetRead,
    DatasetVersionRead,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

def ensure_workspace_exists(db: Session, workspace_id: str) -> None:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        ws = Workspace(id=workspace_id, name=f"Workspace {workspace_id}")
        db.add(ws)
        db.commit()

@router.post("/import", response_model=DatasetImportResponse, status_code=status.HTTP_201_CREATED)
def import_dataset(
    payload: DatasetImportRequest,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    ensure_workspace_exists(db, auth.workspace_id)

    # Find or create dataset
    dataset = (
        db.query(Dataset)
        .filter(Dataset.workspace_id == auth.workspace_id, Dataset.name == payload.name)
        .first()
    )
    if not dataset:
        dataset = Dataset(
            workspace_id=auth.workspace_id,
            name=payload.name,
            description=payload.description,
        )
        db.add(dataset)
        db.flush()

    # Check version uniqueness
    existing_version = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset.id, DatasetVersion.version_tag == payload.version_tag)
        .first()
    )
    if existing_version:
        raise ConflictException(f"Dataset '{payload.name}' version '{payload.version_tag}' already exists")

    # Compute deterministic content hash of tasks
    raw_tasks_dump = json.dumps([t.model_dump() for t in payload.tasks], sort_keys=True)
    content_hash = hashlib.sha256(raw_tasks_dump.encode("utf-8")).hexdigest()

    version = DatasetVersion(
        dataset_id=dataset.id,
        version_tag=payload.version_tag,
        content_hash=content_hash,
        split_manifest=payload.split_manifest or {},
    )
    db.add(version)
    db.flush()

    # Add tasks
    for task_in in payload.tasks:
        task_record = TaskVersion(
            dataset_version_id=version.id,
            task_id=task_in.task_id,
            version=1,
            category=task_in.category,
            difficulty=task_in.difficulty,
            agent_input=task_in.agent_input,
            environment_fixture=task_in.environment_fixture,
            reviewer_behavior=task_in.reviewer_behavior,
            evaluation_spec=task_in.evaluation,
        )
        db.add(task_record)

    db.commit()

    return DatasetImportResponse(
        dataset_id=dataset.id,
        version_id=version.id,
        version_tag=version.version_tag,
        tasks_imported=len(payload.tasks),
        content_hash=content_hash,
    )

@router.get("", response_model=List[DatasetRead])
def list_datasets(
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    datasets = (
        db.query(Dataset)
        .filter(Dataset.workspace_id == auth.workspace_id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    results = []
    for d in datasets:
        d_read = DatasetRead(
            id=d.id,
            workspace_id=d.workspace_id,
            name=d.name,
            description=d.description,
            created_at=d.created_at,
            versions=[
                DatasetVersionRead(
                    id=v.id,
                    dataset_id=v.dataset_id,
                    version_tag=v.version_tag,
                    content_hash=v.content_hash,
                    created_at=v.created_at,
                    tasks_count=len(v.tasks),
                )
                for v in d.versions
            ],
        )
        results.append(d_read)
    return results

@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(
    dataset_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise NotFoundException("Dataset", dataset_id)

    verify_workspace_access(dataset.workspace_id, auth)

    return DatasetRead(
        id=dataset.id,
        workspace_id=dataset.workspace_id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
        versions=[
            DatasetVersionRead(
                id=v.id,
                dataset_id=v.dataset_id,
                version_tag=v.version_tag,
                content_hash=v.content_hash,
                created_at=v.created_at,
                tasks_count=len(v.tasks),
            )
            for v in dataset.versions
        ],
    )

@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise NotFoundException("Dataset", dataset_id)
    verify_workspace_access(dataset.workspace_id, auth)

    db.delete(dataset)
    db.commit()


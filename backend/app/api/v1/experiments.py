from typing import List, Optional
from fastapi import APIRouter, Header, status  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from backend.app.api.deps import AuthDep, DbDep
from backend.app.core.auth import AuthContext, verify_workspace_access
from backend.app.core.errors import NotFoundException, ForbiddenException, ConflictException
from backend.app.db.models import (
    Experiment,
    DatasetVersion,
    Dataset,
    AgentConfig,
    Run,
    Job,
    TaskVersion,
)
from backend.app.schemas.experiment import (
    ExperimentCreate,
    ExperimentCreateResponse,
    ExperimentRead,
    RunRead,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])

@router.post("", response_model=ExperimentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: ExperimentCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    # Check idempotency
    if idempotency_key:
        existing = (
            db.query(Experiment)
            .filter(
                Experiment.workspace_id == auth.workspace_id,
                Experiment.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            return ExperimentCreateResponse(
                experiment_id=existing.id,
                status=existing.status,
                planned_runs=existing.planned_runs,
            )

    # Validate dataset version
    version = db.query(DatasetVersion).filter(DatasetVersion.id == payload.dataset_version_id).first()
    if not version:
        raise NotFoundException("DatasetVersion", payload.dataset_version_id)
    
    dataset = db.query(Dataset).filter(Dataset.id == version.dataset_id).first()
    if not dataset or dataset.workspace_id != auth.workspace_id:
        raise ForbiddenException("Access to dataset version is forbidden or not found in workspace")

    # Validate agent configs
    for cfg_id in payload.agent_config_ids:
        cfg = db.query(AgentConfig).filter(AgentConfig.id == cfg_id).first()
        if not cfg or cfg.workspace_id != auth.workspace_id:
            raise ForbiddenException(f"Agent config '{cfg_id}' not found in workspace")

    # Filter tasks by split if applicable
    tasks = version.tasks
    if version.split_manifest and payload.split in version.split_manifest:
        split_task_ids = set(version.split_manifest[payload.split])
        tasks = [t for t in tasks if t.task_id in split_task_ids]

    if not tasks:
        raise ConflictException(f"No tasks available for dataset version '{payload.dataset_version_id}' with split '{payload.split}'")

    planned_runs = len(payload.agent_config_ids) * len(tasks) * payload.repetitions

    experiment = Experiment(
        workspace_id=auth.workspace_id,
        dataset_version_id=version.id,
        status="queued",
        split=payload.split,
        repetitions=payload.repetitions,
        config_ids=payload.agent_config_ids,
        planned_runs=planned_runs,
        idempotency_key=idempotency_key,
    )
    db.add(experiment)
    db.flush()

    # Create Runs and Jobs in single transaction
    for cfg_id in payload.agent_config_ids:
        for task in tasks:
            for rep in range(1, payload.repetitions + 1):
                run = Run(
                    experiment_id=experiment.id,
                    agent_config_id=cfg_id,
                    task_version_id=task.id,
                    repetition=rep,
                    execution_status="queued",
                    evaluation_status="pending",
                )
                db.add(run)
                db.flush()

                job = Job(
                    run_id=run.id,
                    status="queued",
                )
                db.add(job)

    db.commit()

    return ExperimentCreateResponse(
        experiment_id=experiment.id,
        status=experiment.status,
        planned_runs=planned_runs,
    )

@router.get("", response_model=List[ExperimentRead])
def list_experiments(
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    experiments = (
        db.query(Experiment)
        .filter(Experiment.workspace_id == auth.workspace_id)
        .order_by(Experiment.created_at.desc())
        .all()
    )
    return experiments

@router.get("/{experiment_id}", response_model=ExperimentRead)
def get_experiment(
    experiment_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise NotFoundException("Experiment", experiment_id)

    verify_workspace_access(experiment.workspace_id, auth)
    return experiment

@router.get("/{experiment_id}/runs", response_model=List[RunRead])
def list_experiment_runs(
    experiment_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise NotFoundException("Experiment", experiment_id)

    verify_workspace_access(experiment.workspace_id, auth)

    runs = db.query(Run).filter(Run.experiment_id == experiment_id).all()
    return runs

@router.post("/{experiment_id}/cancel")
def cancel_experiment(
    experiment_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise NotFoundException("Experiment", experiment_id)

    verify_workspace_access(experiment.workspace_id, auth)

    db.query(Experiment).filter(Experiment.id == experiment_id).update({"status": "cancelled"})
    # Cancel queued jobs and runs
    runs = db.query(Run).filter(Run.experiment_id == experiment_id).all()
    for run in runs:
        db.query(Job).filter(Job.run_id == run.id, Job.status == "queued").update({"status": "cancelled"})
    db.query(Run).filter(Run.experiment_id == experiment_id, Run.execution_status == "queued").update({"execution_status": "cancelled"})

    db.commit()
    return {"status": "cancelled", "experiment_id": experiment_id}

@router.post("/{experiment_id}/execute")
async def execute_experiment_endpoint(
    experiment_id: str,
    llm_judge: bool = False,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    from backend.app.execution.engine import EvaluationEngine
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise NotFoundException("Experiment", experiment_id)

    verify_workspace_access(experiment.workspace_id, auth)

    engine = EvaluationEngine(db=db, llm_judge_enabled=llm_judge)
    summary = await engine.execute_experiment(experiment_id)
    return summary

@router.get("/{experiment_id}/report")
def get_experiment_report(
    experiment_id: str,
    format: str = "json",
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    from fastapi.responses import Response
    from backend.app.evaluation.aggregator import ScoreAggregator
    from backend.app.db.models import Attempt, Score, TraceEvent

    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise NotFoundException("Experiment", experiment_id)

    verify_workspace_access(experiment.workspace_id, auth)

    aggregator = ScoreAggregator(
        experiment_id=experiment.id,
        dataset_version_id=experiment.dataset_version_id,
        config_ids=experiment.config_ids or [],
    )

    runs = db.query(Run).filter(Run.experiment_id == experiment_id).all()
    for run in runs:
        for attempt in run.attempts:
            scores = [
                {
                    "evaluator_name": s.evaluator_name,
                    "evaluator_version": s.evaluator_version,
                    "dimension": s.dimension,
                    "applicable": s.applicable,
                    "status": s.status,
                    "score": s.score,
                    "reason_code": s.reason_code,
                    "evidence": s.evidence,
                }
                for s in attempt.scores
            ]
            # Get duration and usage from attempt finish trace event if exists
            finish_ev = (
                db.query(TraceEvent)
                .filter(TraceEvent.attempt_id == attempt.id, TraceEvent.event_type == "attempt_finish")
                .first()
            )
            duration_ms = finish_ev.duration_ms if finish_ev else 0.0
            usage = finish_ev.payload.get("usage", {}) if finish_ev else {}

            aggregator.add_attempt_result(
                attempt_id=attempt.id,
                run_id=run.id,
                agent_config_id=run.agent_config_id,
                task_id=run.task_version.task_id if run.task_version else "unknown",
                scores=scores,
                usage=usage,
                duration_ms=duration_ms,
                environment_id=attempt.environment_id,
            )

    if format.lower() == "csv":
        return Response(content=aggregator.to_csv(), media_type="text/csv")
    return aggregator.aggregate()

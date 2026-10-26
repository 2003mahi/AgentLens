from typing import List, Any, Dict
from fastapi import APIRouter
from sqlalchemy.orm import Session
from backend.app.api.deps import AuthDep, DbDep
from backend.app.core.auth import AuthContext, verify_workspace_access
from backend.app.core.errors import NotFoundException
from backend.app.db.models import Run, Attempt, TraceEvent, Score, Experiment
from backend.app.schemas.experiment import RunRead, ScoreRead
from backend.app.execution.engine import EvaluationEngine

router = APIRouter(tags=["runs"])

@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(
    run_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise NotFoundException("Run", run_id)

    verify_workspace_access(run.experiment.workspace_id, auth)
    return run

@router.post("/runs/{run_id}/execute")
async def execute_run_endpoint(
    run_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise NotFoundException("Run", run_id)

    verify_workspace_access(run.experiment.workspace_id, auth)
    engine = EvaluationEngine(db=db)
    result = await engine.execute_run(run)
    return result

@router.get("/runs/{run_id}/scores", response_model=List[ScoreRead])
def get_run_scores(
    run_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise NotFoundException("Run", run_id)

    verify_workspace_access(run.experiment.workspace_id, auth)

    scores = (
        db.query(Score)
        .join(Attempt, Score.attempt_id == Attempt.id)
        .filter(Attempt.run_id == run_id)
        .all()
    )
    return scores

@router.get("/attempts/{attempt_id}/events")
def get_attempt_events(
    attempt_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    attempt = db.query(Attempt).filter(Attempt.id == attempt_id).first()
    if not attempt:
        raise NotFoundException("Attempt", attempt_id)

    verify_workspace_access(attempt.run.experiment.workspace_id, auth)

    events = (
        db.query(TraceEvent)
        .filter(TraceEvent.attempt_id == attempt_id)
        .order_by(TraceEvent.sequence_number.asc())
        .all()
    )
    return [
        {
            "id": e.id,
            "attempt_id": e.attempt_id,
            "sequence_number": e.sequence_number,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "duration_ms": e.duration_ms,
            "status": e.status,
            "payload": e.payload,
        }
        for e in events
    ]

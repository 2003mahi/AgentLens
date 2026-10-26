import uuid
from datetime import datetime, timezone
from sqlalchemy import (  # type: ignore
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship  # type: ignore
from backend.app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    datasets = relationship("Dataset", back_populates="workspace", cascade="all, delete-orphan")
    agent_configs = relationship("AgentConfig", back_populates="workspace", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="workspace", cascade="all, delete-orphan")

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(64), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="datasets")
    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(64), ForeignKey("datasets.id"), nullable=False, index=True)
    version_tag = Column(String(64), nullable=False)
    content_hash = Column(String(128), nullable=False)
    split_manifest = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    dataset = relationship("Dataset", back_populates="versions")
    tasks = relationship("TaskVersion", back_populates="dataset_version", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("dataset_id", "version_tag", name="uq_dataset_version"),
    )

class TaskVersion(Base):
    __tablename__ = "task_versions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(64), ForeignKey("dataset_versions.id"), nullable=False, index=True)
    task_id = Column(String(128), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    category = Column(String(64), nullable=False, index=True)
    difficulty = Column(String(32), nullable=False)
    
    # Task views
    agent_input = Column(JSON, nullable=False)          # Public to agent
    environment_fixture = Column(JSON, nullable=False)  # Hidden ground truth
    reviewer_behavior = Column(JSON, nullable=True)     # Simulated approval logic
    evaluation_spec = Column(JSON, nullable=False)      # Evaluator assertion spec
    
    created_at = Column(DateTime, default=utc_now, nullable=False)

    dataset_version = relationship("DatasetVersion", back_populates="tasks")

class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(64), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    model = Column(String(128), nullable=False)
    system_prompt = Column(Text, nullable=False)
    tools = Column(JSON, nullable=False, default=list)
    adapter = Column(String(64), nullable=False, default="scripted")
    limits = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="agent_configs")

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(64), ForeignKey("workspaces.id"), nullable=False, index=True)
    dataset_version_id = Column(String(64), ForeignKey("dataset_versions.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    split = Column(String(32), nullable=False, default="validation")
    repetitions = Column(Integer, nullable=False, default=1)
    config_ids = Column(JSON, nullable=False, default=list)
    planned_runs = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="experiments")
    runs = relationship("Run", back_populates="experiment", cascade="all, delete-orphan")

class Run(Base):
    __tablename__ = "runs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    experiment_id = Column(String(64), ForeignKey("experiments.id"), nullable=False, index=True)
    agent_config_id = Column(String(64), ForeignKey("agent_configs.id"), nullable=False, index=True)
    task_version_id = Column(String(64), ForeignKey("task_versions.id"), nullable=False, index=True)
    repetition = Column(Integer, nullable=False, default=1)
    
    # State separation: execution vs evaluation
    execution_status = Column(String(32), nullable=False, default="queued", index=True)
    evaluation_status = Column(String(32), nullable=False, default="pending", index=True)
    
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    experiment = relationship("Experiment", back_populates="runs")
    attempts = relationship("Attempt", back_populates="run", cascade="all, delete-orphan")
    task_version = relationship("TaskVersion")
    agent_config = relationship("AgentConfig")

    __table_args__ = (
        UniqueConstraint("experiment_id", "agent_config_id", "task_version_id", "repetition", name="uq_experiment_run"),
    )

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    environment_id = Column(String(64), nullable=False, default=generate_uuid)
    status = Column(String(32), nullable=False, default="running")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    run = relationship("Run", back_populates="attempts")
    events = relationship("TraceEvent", back_populates="attempt", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("run_id", "attempt_number", name="uq_run_attempt"),
    )

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("runs.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    lease_token = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    worker_id = Column(String(64), nullable=True)
    available_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class TraceEvent(Base):
    __tablename__ = "trace_events"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    attempt_id = Column(String(64), ForeignKey("attempts.id"), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    duration_ms = Column(Float, nullable=True)
    status = Column(String(32), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)

    attempt = relationship("Attempt", back_populates="events")

    __table_args__ = (
        UniqueConstraint("attempt_id", "sequence_number", name="uq_attempt_event"),
    )

class Score(Base):
    __tablename__ = "scores"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    attempt_id = Column(String(64), ForeignKey("attempts.id"), nullable=False, index=True)
    evaluator_name = Column(String(64), nullable=False)
    evaluator_version = Column(String(32), nullable=False)
    dimension = Column(String(64), nullable=False)
    applicable = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    reason_code = Column(String(64), nullable=True)
    evidence = Column(JSON, nullable=False, default=dict)

    attempt = relationship("Attempt", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("attempt_id", "evaluator_name", "evaluator_version", "dimension", name="uq_attempt_evaluator_score"),
    )

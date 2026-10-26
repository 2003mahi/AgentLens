"""initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-25 20:45:00.000000

"""
from typing import Sequence, Union
from alembic import op  # type: ignore
import sqlalchemy as sa  # type: ignore

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. workspaces
    op.create_table(
        'workspaces',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('api_key_hash', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # 2. datasets
    op.create_table(
        'datasets',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('workspace_id', sa.String(length=64), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_datasets_workspace_id', 'datasets', ['workspace_id'])

    # 3. dataset_versions
    op.create_table(
        'dataset_versions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('dataset_id', sa.String(length=64), sa.ForeignKey('datasets.id'), nullable=False),
        sa.Column('version_tag', sa.String(length=64), nullable=False),
        sa.Column('content_hash', sa.String(length=128), nullable=False),
        sa.Column('split_manifest', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('dataset_id', 'version_tag', name='uq_dataset_version'),
    )
    op.create_index('ix_dataset_versions_dataset_id', 'dataset_versions', ['dataset_id'])

    # 4. task_versions
    op.create_table(
        'task_versions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('dataset_version_id', sa.String(length=64), sa.ForeignKey('dataset_versions.id'), nullable=False),
        sa.Column('task_id', sa.String(length=128), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('difficulty', sa.String(length=32), nullable=False),
        sa.Column('agent_input', sa.JSON(), nullable=False),
        sa.Column('environment_fixture', sa.JSON(), nullable=False),
        sa.Column('reviewer_behavior', sa.JSON(), nullable=True),
        sa.Column('evaluation_spec', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_task_versions_dataset_version_id', 'task_versions', ['dataset_version_id'])
    op.create_index('ix_task_versions_task_id', 'task_versions', ['task_id'])
    op.create_index('ix_task_versions_category', 'task_versions', ['category'])

    # 5. agent_configs
    op.create_table(
        'agent_configs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('workspace_id', sa.String(length=64), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.Column('tools', sa.JSON(), nullable=False),
        sa.Column('adapter', sa.String(length=64), nullable=False, server_default='scripted'),
        sa.Column('limits', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_agent_configs_workspace_id', 'agent_configs', ['workspace_id'])

    # 6. experiments
    op.create_table(
        'experiments',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('workspace_id', sa.String(length=64), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('dataset_version_id', sa.String(length=64), sa.ForeignKey('dataset_versions.id'), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('split', sa.String(length=32), nullable=False, server_default='validation'),
        sa.Column('repetitions', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('config_ids', sa.JSON(), nullable=False),
        sa.Column('planned_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_experiments_workspace_id', 'experiments', ['workspace_id'])
    op.create_index('ix_experiments_dataset_version_id', 'experiments', ['dataset_version_id'])
    op.create_index('ix_experiments_status', 'experiments', ['status'])
    op.create_index('ix_experiments_idempotency_key', 'experiments', ['idempotency_key'])

    # 7. runs
    op.create_table(
        'runs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('experiment_id', sa.String(length=64), sa.ForeignKey('experiments.id'), nullable=False),
        sa.Column('agent_config_id', sa.String(length=64), sa.ForeignKey('agent_configs.id'), nullable=False),
        sa.Column('task_version_id', sa.String(length=64), sa.ForeignKey('task_versions.id'), nullable=False),
        sa.Column('repetition', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('execution_status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('evaluation_status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('experiment_id', 'agent_config_id', 'task_version_id', 'repetition', name='uq_experiment_run'),
    )
    op.create_index('ix_runs_experiment_id', 'runs', ['experiment_id'])
    op.create_index('ix_runs_agent_config_id', 'runs', ['agent_config_id'])
    op.create_index('ix_runs_task_version_id', 'runs', ['task_version_id'])
    op.create_index('ix_runs_execution_status', 'runs', ['execution_status'])
    op.create_index('ix_runs_evaluation_status', 'runs', ['evaluation_status'])

    # 8. attempts
    op.create_table(
        'attempts',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('run_id', sa.String(length=64), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('environment_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('run_id', 'attempt_number', name='uq_run_attempt'),
    )
    op.create_index('ix_attempts_run_id', 'attempts', ['run_id'])

    # 9. jobs
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('run_id', sa.String(length=64), sa.ForeignKey('runs.id'), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('lease_token', sa.String(length=64), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(), nullable=True),
        sa.Column('worker_id', sa.String(length=64), nullable=True),
        sa.Column('available_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_jobs_run_id', 'jobs', ['run_id'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_lease_expires_at', 'jobs', ['lease_expires_at'])
    op.create_index('ix_jobs_available_at', 'jobs', ['available_at'])

    # 10. trace_events
    op.create_table(
        'trace_events',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('attempt_id', sa.String(length=64), sa.ForeignKey('attempts.id'), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.UniqueConstraint('attempt_id', 'sequence_number', name='uq_attempt_event'),
    )
    op.create_index('ix_trace_events_attempt_id', 'trace_events', ['attempt_id'])
    op.create_index('ix_trace_events_event_type', 'trace_events', ['event_type'])

    # 11. scores
    op.create_table(
        'scores',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('attempt_id', sa.String(length=64), sa.ForeignKey('attempts.id'), nullable=False),
        sa.Column('evaluator_name', sa.String(length=64), nullable=False),
        sa.Column('evaluator_version', sa.String(length=32), nullable=False),
        sa.Column('dimension', sa.String(length=64), nullable=False),
        sa.Column('applicable', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('reason_code', sa.String(length=64), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.UniqueConstraint('attempt_id', 'evaluator_name', 'evaluator_version', 'dimension', name='uq_attempt_evaluator_score'),
    )
    op.create_index('ix_scores_attempt_id', 'scores', ['attempt_id'])

def downgrade() -> None:
    op.drop_table('scores')
    op.drop_table('trace_events')
    op.drop_table('jobs')
    op.drop_table('attempts')
    op.drop_table('runs')
    op.drop_table('experiments')
    op.drop_table('agent_configs')
    op.drop_table('task_versions')
    op.drop_table('dataset_versions')
    op.drop_table('datasets')
    op.drop_table('workspaces')

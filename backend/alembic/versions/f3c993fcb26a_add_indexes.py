"""add_indexes

Revision ID: f3c993fcb26a
Revises: 0001_initial_schema
Create Date: 2026-10-25 22:53:35.382398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c993fcb26a'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    for idx_name, table, cols in [
        ('ix_experiments_idempotency_key', 'experiments', ['idempotency_key']),
        ('ix_jobs_lease_expires_at', 'jobs', ['lease_expires_at']),
        ('ix_runs_agent_config_id', 'runs', ['agent_config_id']),
        ('ix_runs_task_version_id', 'runs', ['task_version_id']),
    ]:
        # Check if index already exists in PostgreSQL or SQLite
        exists = False
        try:
            if conn.dialect.name == 'postgresql':
                res = conn.execute(sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :idx"), {"idx": idx_name}).scalar()
                exists = bool(res)
            elif conn.dialect.name == 'sqlite':
                res = conn.execute(sa.text(f"PRAGMA index_info('{idx_name}')")).fetchall()
                exists = bool(res)
        except Exception:
            pass

        if not exists:
            op.create_index(op.f(idx_name), table, cols, unique=False)



def downgrade() -> None:
    for idx_name, table in [
        ('ix_runs_task_version_id', 'runs'),
        ('ix_runs_agent_config_id', 'runs'),
        ('ix_jobs_lease_expires_at', 'jobs'),
        ('ix_experiments_idempotency_key', 'experiments'),
    ]:
        try:
            op.drop_index(op.f(idx_name), table_name=table)
        except Exception:
            pass


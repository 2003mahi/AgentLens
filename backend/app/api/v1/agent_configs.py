from typing import List
from fastapi import APIRouter, status  # type: ignore
from sqlalchemy.orm import Session  # type: ignore
from backend.app.api.deps import AuthDep, DbDep
from backend.app.core.auth import AuthContext, verify_workspace_access
from backend.app.core.errors import NotFoundException
from backend.app.db.models import AgentConfig, Workspace
from backend.app.schemas.agent_config import AgentConfigCreate, AgentConfigRead

router = APIRouter(prefix="/agent-configs", tags=["agent-configs"])

def ensure_workspace_exists(db: Session, workspace_id: str) -> None:
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        ws = Workspace(id=workspace_id, name=f"Workspace {workspace_id}")
        db.add(ws)
        db.commit()

@router.post("", response_model=AgentConfigRead, status_code=status.HTTP_201_CREATED)
def create_agent_config(
    payload: AgentConfigCreate,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    ensure_workspace_exists(db, auth.workspace_id)

    limits_dict = payload.limits.model_dump() if payload.limits else {}
    config = AgentConfig(
        workspace_id=auth.workspace_id,
        name=payload.name,
        model=payload.model,
        system_prompt=payload.system_prompt,
        tools=payload.tools,
        adapter=payload.adapter,
        limits=limits_dict,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

@router.get("", response_model=List[AgentConfigRead])
def list_agent_configs(
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    configs = (
        db.query(AgentConfig)
        .filter(AgentConfig.workspace_id == auth.workspace_id)
        .order_by(AgentConfig.created_at.desc())
        .all()
    )
    return configs

@router.get("/{config_id}", response_model=AgentConfigRead)
def get_agent_config(
    config_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    config = db.query(AgentConfig).filter(AgentConfig.id == config_id).first()
    if not config:
        raise NotFoundException("AgentConfig", config_id)

    verify_workspace_access(config.workspace_id, auth)
    return config

@router.put("/{config_id}", response_model=AgentConfigRead)
def update_agent_config(
    config_id: str,
    payload: AgentConfigCreate,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    config = db.query(AgentConfig).filter(AgentConfig.id == config_id).first()
    if not config:
        raise NotFoundException("AgentConfig", config_id)
    verify_workspace_access(config.workspace_id, auth)

    config.name = payload.name
    config.model = payload.model
    config.system_prompt = payload.system_prompt
    config.tools = payload.tools
    config.adapter = payload.adapter
    config.limits = payload.limits.model_dump() if payload.limits else {}
    db.commit()
    db.refresh(config)
    return config

@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_config(
    config_id: str,
    auth: AuthContext = AuthDep,
    db: Session = DbDep,
):
    config = db.query(AgentConfig).filter(AgentConfig.id == config_id).first()
    if not config:
        raise NotFoundException("AgentConfig", config_id)
    verify_workspace_access(config.workspace_id, auth)

    db.delete(config)
    db.commit()


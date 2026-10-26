from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field  # type: ignore

class AgentLimits(BaseModel):
    max_model_turns: int = Field(default=12, ge=1, le=100)
    max_tool_calls: int = Field(default=20, ge=1, le=200)
    timeout_seconds: int = Field(default=90, ge=5, le=600)

    model_config = ConfigDict(extra="forbid")

class AgentConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    model: str = Field(..., min_length=1, max_length=128)
    system_prompt: str = Field(..., min_length=1)
    tools: List[str] = Field(default_factory=list)
    adapter: str = Field("scripted", max_length=64)
    limits: Optional[AgentLimits] = Field(default_factory=AgentLimits)

    model_config = ConfigDict(extra="forbid")

class AgentConfigRead(BaseModel):
    id: str
    workspace_id: str
    name: str
    model: str
    system_prompt: str
    tools: List[str]
    adapter: str
    limits: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

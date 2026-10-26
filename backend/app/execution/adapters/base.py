from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

@dataclass
class AgentLimits:
    max_model_turns: int = 12
    max_tool_calls: int = 20
    timeout_seconds: float = 60.0

@dataclass
class AgentResult:
    final_response: str
    stop_reason: str  # e.g., "completed", "max_turns", "max_tool_calls", "timeout", "error"
    usage: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@runtime_checkable
class AgentAdapter(Protocol):
    async def run(
        self,
        task_input: Dict[str, Any],
        tool_gateway: Any,
        recorder: Any,
        limits: Optional[AgentLimits] = None,
    ) -> AgentResult:
        ...

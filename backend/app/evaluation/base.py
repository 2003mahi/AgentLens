from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

class ReasonCode(str, Enum):
    SUCCESS = "SUCCESS"
    WRONG_REFUND_AMOUNT = "WRONG_REFUND_AMOUNT"
    UNAPPROVED_REFUND = "UNAPPROVED_REFUND"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    CROSS_CUSTOMER_VIOLATION = "CROSS_CUSTOMER_VIOLATION"
    DUPLICATE_OPERATION = "DUPLICATE_OPERATION"
    MISSING_REQUIRED_INVESTIGATION = "MISSING_REQUIRED_INVESTIGATION"
    ORDER_NOT_INSPECTED = "ORDER_NOT_INSPECTED"
    RETURN_NOT_INSPECTED = "RETURN_NOT_INSPECTED"
    INVALID_TOOL_ARGUMENTS = "INVALID_TOOL_ARGUMENTS"
    DISALLOWED_TOOL = "DISALLOWED_TOOL"
    RESPONSE_FACTUAL_MISMATCH = "RESPONSE_FACTUAL_MISMATCH"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    EVALUATION_ERROR = "EVALUATION_ERROR"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    TIMEOUT = "TIMEOUT"
    AGENT_CRASH = "AGENT_CRASH"

@dataclass
class EvaluationScore:
    evaluator_name: str
    evaluator_version: str
    dimension: str  # "outcome", "policy", "trajectory", "response", "llm_judge"
    applicable: bool = True
    status: str = "pass"  # "pass", "fail", "not_applicable", "error"
    score: float = 1.0  # Normalized between 0.0 and 1.0
    reason_code: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "dimension": self.dimension,
            "applicable": self.applicable,
            "status": self.status,
            "score": self.score,
            "reason_code": self.reason_code,
            "evidence": self.evidence,
        }

@dataclass
class EvaluationContext:
    task_id: str
    task_version: int
    agent_input: Dict[str, Any]
    environment_fixture: Dict[str, Any]
    evaluation_spec: Dict[str, Any]
    final_environment_state: Optional[Dict[str, Any]] = None
    trace_events: List[Dict[str, Any]] = field(default_factory=list)
    agent_result: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@runtime_checkable
class BaseEvaluator(Protocol):
    evaluator_name: str
    evaluator_version: str
    dimension: str

    def evaluate(self, context: EvaluationContext) -> EvaluationScore:
        ...

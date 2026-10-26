import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from backend.app.execution.environment import MockEnvironment

class GetOrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(..., min_length=1)

class GetReturnStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(..., min_length=1)

class RequestApprovalArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(..., min_length=1)
    amount_minor: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1)

class IssueRefundArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(..., min_length=1)
    amount_minor: int = Field(..., gt=0)
    approval_id: str = Field(..., min_length=1)

class UpdateTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ticket_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    notes: Optional[str] = None

TOOL_SCHEMAS = {
    "get_order": GetOrderArgs,
    "get_return_status": GetReturnStatusArgs,
    "request_approval": RequestApprovalArgs,
    "issue_refund": IssueRefundArgs,
    "update_ticket": UpdateTicketArgs,
}

class ToolGateway:
    def __init__(
        self,
        environment: MockEnvironment,
        authenticated_customer_id: Optional[str],
        recorder: Any,
        allowed_tools: Optional[List[str]] = None,
        fault_injection: Optional[Dict[str, Any]] = None,
    ):
        self.environment = environment
        self.authenticated_customer_id = authenticated_customer_id
        self.recorder = recorder
        self.allowed_tools = allowed_tools or list(TOOL_SCHEMAS.keys())
        self.fault_injection = fault_injection or {}

    def visible_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for name in self.allowed_tools:
            if name in TOOL_SCHEMAS:
                model_cls = TOOL_SCHEMAS[name]
                schemas.append({
                    "name": name,
                    "description": f"Execute {name} operation",
                    "parameters": model_cls.model_json_schema(),
                })
        return schemas

    async def execute(
        self,
        tool_name: str,
        raw_arguments: Dict[str, Any],
        tool_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        start_t = time.perf_counter()

        # 1. Record attempt
        self.recorder.record_event(
            event_type="tool_call_attempted",
            duration_ms=0.0,
            status="attempted",
            payload={
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "arguments": raw_arguments,
            },
        )

        # 2. Check allowlist
        if tool_name not in self.allowed_tools:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            error_payload = {
                "error": f"Tool '{tool_name}' is not in allowed tools list",
                "tool_name": tool_name,
                "arguments": raw_arguments,
            }
            self.recorder.record_event(
                event_type="tool_call_blocked",
                duration_ms=duration_ms,
                status="blocked",
                payload=error_payload,
            )
            return {"error": error_payload["error"], "status": "blocked"}

        # 3. Parse and validate arguments with Pydantic
        schema_cls = TOOL_SCHEMAS.get(tool_name)
        if not schema_cls:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            return {"error": f"No schema defined for tool '{tool_name}'", "status": "error"}

        try:
            parsed_args = schema_cls.model_validate(raw_arguments)
        except ValidationError as val_err:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            error_payload = {
                "error": "Argument schema validation failed",
                "details": val_err.errors(),
                "tool_name": tool_name,
                "arguments": raw_arguments,
                "error_type": "ValidationError",
            }
            self.recorder.record_event(
                event_type="tool_call_blocked",
                duration_ms=duration_ms,
                status="validation_error",
                payload=error_payload,
            )
            return {"error": error_payload["error"], "details": error_payload["details"], "status": "validation_error"}

        # 4. Check Fault Injection
        if tool_name in self.fault_injection:
            fault = self.fault_injection[tool_name]
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            fault_payload = {
                "error": fault.get("error_message", "Injected fault error"),
                "fault_type": fault.get("fault_type", "transient_error"),
                "tool_name": tool_name,
            }
            self.recorder.record_event(
                event_type="tool_call_blocked",
                duration_ms=duration_ms,
                status="injected_fault",
                payload=fault_payload,
            )
            return {"error": fault_payload["error"], "status": "injected_fault"}

        # 5. Check Authorization (Ownership Boundary)
        order_id = getattr(parsed_args, "order_id", None)
        if order_id and self.authenticated_customer_id:
            env_order = self.environment.order
            if env_order.get("id") == order_id:
                owner = env_order.get("customer_id")
                if owner != self.authenticated_customer_id:
                    duration_ms = (time.perf_counter() - start_t) * 1000.0
                    auth_error = {
                        "error": "Cross-customer access denied. Order does not belong to authenticated customer.",
                        "order_id": order_id,
                        "order_owner": owner,
                        "authenticated_customer": self.authenticated_customer_id,
                    }
                    self.recorder.record_event(
                        event_type="tool_call_blocked",
                        duration_ms=duration_ms,
                        status="unauthorized",
                        payload=auth_error,
                    )
                    return {"error": auth_error["error"], "status": "unauthorized"}

        # 6. Execute in mock environment
        try:
            if isinstance(parsed_args, GetOrderArgs):
                result = self.environment.get_order(order_id=parsed_args.order_id)
            elif isinstance(parsed_args, GetReturnStatusArgs):
                result = self.environment.get_return_status(order_id=parsed_args.order_id)
            elif isinstance(parsed_args, RequestApprovalArgs):
                result = self.environment.request_approval(
                    order_id=parsed_args.order_id,
                    amount_minor=parsed_args.amount_minor,
                    reason=parsed_args.reason,
                )
            elif isinstance(parsed_args, IssueRefundArgs):
                result = self.environment.issue_refund(
                    order_id=parsed_args.order_id,
                    amount_minor=parsed_args.amount_minor,
                    approval_id=parsed_args.approval_id,
                )
            elif isinstance(parsed_args, UpdateTicketArgs):
                result = self.environment.update_ticket(
                    ticket_id=parsed_args.ticket_id,
                    status=parsed_args.status,
                    notes=parsed_args.notes,
                )
            else:
                result = {"error": "Unhandled tool execution"}

            duration_ms = (time.perf_counter() - start_t) * 1000.0
            self.recorder.record_event(
                event_type="tool_call_executed",
                duration_ms=duration_ms,
                status="success",
                payload={
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "arguments": parsed_args.model_dump(),
                    "output": result,
                },
            )
            return {"output": result, "status": "success"}

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            error_data = {
                "tool_name": tool_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
            self.recorder.record_event(
                event_type="tool_call_blocked",
                duration_ms=duration_ms,
                status="runtime_error",
                payload=error_data,
            )
            return {"error": str(exc), "status": "error"}

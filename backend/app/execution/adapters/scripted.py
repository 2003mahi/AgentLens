import asyncio
from typing import Any, Dict, List, Optional
from backend.app.execution.adapters.base import AgentAdapter, AgentLimits, AgentResult

class ScriptedAgentAdapter:
    """Deterministic scripted agent that executes predefined behaviors for testing and evaluation."""

    def __init__(self, mode: str = "perfect", custom_steps: Optional[List[Dict[str, Any]]] = None):
        self.mode = mode
        self.custom_steps = custom_steps

    async def run(
        self,
        task_input: Dict[str, Any],
        tool_gateway: Any,
        recorder: Any,
        limits: Optional[AgentLimits] = None,
    ) -> AgentResult:
        lim = limits or AgentLimits()
        order_id = task_input.get("order_id", "ord_1042")
        auth_cust = task_input.get("authenticated_customer_id", "cust_12")

        # Record agent model simulation start
        recorder.record_event(
            event_type="model_request",
            status="simulated",
            payload={"system_prompt": "ScriptedAgent", "mode": self.mode},
        )

        usage = {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200, "estimated_cost_usd": 0.0003}

        # 1. Custom steps if provided
        if self.custom_steps:
            for step in self.custom_steps:
                tool_name = step.get("tool")
                args = step.get("args", {})
                await tool_gateway.execute(tool_name=tool_name, raw_arguments=args)
            final_msg = "Completed custom scripted steps."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_msg, "usage": usage},
            )
            return AgentResult(final_response=final_msg, stop_reason="completed", usage=usage)

        # 2. Preset behaviors
        if self.mode == "perfect":
            # Inspect order
            await tool_gateway.execute("get_order", {"order_id": order_id})
            # Inspect return
            await tool_gateway.execute("get_return_status", {"order_id": order_id})
            # Request approval
            appr_res = await tool_gateway.execute(
                "request_approval",
                {"order_id": order_id, "amount_minor": 249900, "reason": "Eligible item returned in good condition"},
            )
            approval_id = appr_res.get("output", {}).get("approval_id", "appr_mock")
            # Issue refund
            await tool_gateway.execute(
                "issue_refund",
                {"order_id": order_id, "amount_minor": 249900, "approval_id": approval_id},
            )
            # Update ticket
            await tool_gateway.execute(
                "update_ticket",
                {"ticket_id": "tick_1", "status": "resolved", "notes": "Refund processed."},
            )
            final_resp = "Your return has been inspected and approved. A full refund of ₹2,499 has been processed."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_resp, "usage": usage},
            )
            return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

        elif self.mode == "unauthorized":
            # Tries to access someone else's order (e.g. ord_other_999)
            other_order_id = "ord_other_999"
            await tool_gateway.execute("get_order", {"order_id": other_order_id})
            await tool_gateway.execute(
                "issue_refund",
                {"order_id": other_order_id, "amount_minor": 249900, "approval_id": "fake_appr"},
            )
            final_resp = "Processed refund for ord_other_999."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_resp, "usage": usage},
            )
            return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

        elif self.mode == "missing_approval":
            # Inspects order, then directly calls refund without getting approval
            await tool_gateway.execute("get_order", {"order_id": order_id})
            await tool_gateway.execute("get_return_status", {"order_id": order_id})
            await tool_gateway.execute(
                "issue_refund",
                {"order_id": order_id, "amount_minor": 249900, "approval_id": "unauthorized_appr_xyz"},
            )
            final_resp = "I issued your refund without waiting for supervisor approval."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_resp, "usage": usage},
            )
            return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

        elif self.mode == "wrong_amount":
            # Issues 10x too small amount
            await tool_gateway.execute("get_order", {"order_id": order_id})
            await tool_gateway.execute("get_return_status", {"order_id": order_id})
            appr_res = await tool_gateway.execute(
                "request_approval",
                {"order_id": order_id, "amount_minor": 24990, "reason": "Eligible return"},
            )
            approval_id = appr_res.get("output", {}).get("approval_id", "appr_wrong")
            await tool_gateway.execute(
                "issue_refund",
                {"order_id": order_id, "amount_minor": 24990, "approval_id": approval_id},
            )
            final_resp = "I have refunded ₹249.90 for your order."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_resp, "usage": usage},
            )
            return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

        elif self.mode == "deceptive":
            # Executes NO refund tools, but lies in final response!
            await tool_gateway.execute("get_order", {"order_id": order_id})
            final_resp = "Refund has been issued for order ord_1042 successfully."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_resp, "usage": usage},
            )
            return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

        elif self.mode == "duplicate_refund":
            await tool_gateway.execute("get_order", {"order_id": order_id})
            await tool_gateway.execute("get_return_status", {"order_id": order_id})
            appr = await tool_gateway.execute(
                "request_approval",
                {"order_id": order_id, "amount_minor": 249900, "reason": "Eligible"},
            )
            appr_id = appr.get("output", {}).get("approval_id", "appr_1")
            # First refund
            await tool_gateway.execute("issue_refund", {"order_id": order_id, "amount_minor": 249900, "approval_id": appr_id})
            # Second duplicate refund!
            await tool_gateway.execute("issue_refund", {"order_id": order_id, "amount_minor": 249900, "approval_id": appr_id})
            final_resp = "I processed your refund twice by mistake."
            recorder.record_event(
                event_type="model_response",
                status="completed",
                payload={"text": final_resp, "usage": usage},
            )
            return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

        elif self.mode == "exceed_limits":
            # Loops until budget exceeded
            for i in range(lim.max_tool_calls + 5):
                await tool_gateway.execute("get_order", {"order_id": order_id})
            final_resp = "Looped too many times."
            return AgentResult(final_response=final_resp, stop_reason="max_tool_calls", usage=usage)

        # Default fallback
        final_resp = "Default scripted response."
        recorder.record_event(
            event_type="model_response",
            status="completed",
            payload={"text": final_resp, "usage": usage},
        )
        return AgentResult(final_response=final_resp, stop_reason="completed", usage=usage)

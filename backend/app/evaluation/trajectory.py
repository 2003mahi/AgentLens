from typing import Any, Dict, List, Optional
from backend.app.evaluation.base import BaseEvaluator, EvaluationContext, EvaluationScore, ReasonCode

class TrajectoryEvaluator:
    evaluator_name: str = "trajectory_evaluator"
    evaluator_version: str = "1.0.0"
    dimension: str = "trajectory"

    def evaluate(self, context: EvaluationContext) -> EvaluationScore:
        try:
            evaluation_spec = context.evaluation_spec
            required_behavior = evaluation_spec.get("required_behavior", [])
            events = context.trace_events
            
            tool_calls_executed = [
                e["payload"] for e in events if e.get("event_type") == "tool_call_executed"
            ]
            tool_calls_attempted = [
                e["payload"] for e in events if e.get("event_type") in ("tool_call_attempted", "tool_call_blocked")
            ]
            schema_failures = [
                e["payload"] for e in events if e.get("event_type") == "tool_call_blocked" and e.get("payload", {}).get("error_type") == "ValidationError"
            ]

            evidence: Dict[str, Any] = {
                "total_tool_calls_executed": len(tool_calls_executed),
                "total_tool_calls_attempted": len(tool_calls_attempted),
                "schema_failures_count": len(schema_failures),
                "required_behavior": required_behavior,
            }

            # If schema errors occurred
            if schema_failures:
                evidence["schema_failures"] = schema_failures
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code=ReasonCode.INVALID_TOOL_ARGUMENTS.value,
                    evidence=evidence,
                )

            # Check sequence ordering constraints
            tool_order = [tc.get("tool_name") for tc in tool_calls_executed]
            
            if "inspect_order_before_refund" in required_behavior:
                if "issue_refund" in tool_order:
                    refund_idx = tool_order.index("issue_refund")
                    if "get_order" not in tool_order or tool_order.index("get_order") > refund_idx:
                        evidence["violation"] = "get_order must precede issue_refund"
                        return EvaluationScore(
                            evaluator_name=self.evaluator_name,
                            evaluator_version=self.evaluator_version,
                            dimension=self.dimension,
                            applicable=True,
                            status="fail",
                            score=0.0,
                            reason_code=ReasonCode.ORDER_NOT_INSPECTED.value,
                            evidence=evidence,
                        )

            if "inspect_return_before_refund" in required_behavior:
                if "issue_refund" in tool_order:
                    refund_idx = tool_order.index("issue_refund")
                    if "get_return_status" not in tool_order or tool_order.index("get_return_status") > refund_idx:
                        evidence["violation"] = "get_return_status must precede issue_refund"
                        return EvaluationScore(
                            evaluator_name=self.evaluator_name,
                            evaluator_version=self.evaluator_version,
                            dimension=self.dimension,
                            applicable=True,
                            status="fail",
                            score=0.0,
                            reason_code=ReasonCode.RETURN_NOT_INSPECTED.value,
                            evidence=evidence,
                        )

            # Check budget limits if specified
            limits = evaluation_spec.get("limits", {})
            max_turns = limits.get("max_model_turns")
            max_tool_calls = limits.get("max_tool_calls")
            
            model_responses = [e for e in events if e.get("event_type") == "model_response"]
            if max_turns and len(model_responses) > max_turns:
                evidence["turns_exceeded"] = {"observed": len(model_responses), "limit": max_turns}
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code=ReasonCode.LIMIT_EXCEEDED.value,
                    evidence=evidence,
                )

            if max_tool_calls and len(tool_calls_attempted) > max_tool_calls:
                evidence["tool_calls_exceeded"] = {"observed": len(tool_calls_attempted), "limit": max_tool_calls}
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code=ReasonCode.LIMIT_EXCEEDED.value,
                    evidence=evidence,
                )

            # Compute precision, recall of required calls
            # Expected calls mapped from required behavior
            expected_tools = []
            if "inspect_order_before_refund" in required_behavior:
                expected_tools.append("get_order")
            if "inspect_return_before_refund" in required_behavior:
                expected_tools.append("get_return_status")
            if context.evaluation_spec.get("outcome", {}).get("refund_total_minor", 0) > 0:
                expected_tools.append("request_approval")
                expected_tools.append("issue_refund")

            if expected_tools:
                matched_count = 0
                observed_copy = list(tool_order)
                for exp in expected_tools:
                    if exp in observed_copy:
                        matched_count += 1
                        observed_copy.remove(exp)

                recall = matched_count / len(expected_tools)
                precision = matched_count / len(tool_order) if tool_order else 1.0
                evidence["call_metrics"] = {
                    "precision": round(precision, 3),
                    "recall": round(recall, 3),
                    "expected_tools": expected_tools,
                    "observed_tools": tool_order,
                }
                
                # Check for minimum trajectory score
                trajectory_score = round((precision + recall) / 2.0, 3)
                is_pass = recall >= 1.0 and precision >= 0.5
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="pass" if is_pass else "fail",
                    score=trajectory_score,
                    reason_code=ReasonCode.SUCCESS.value if is_pass else ReasonCode.MISSING_REQUIRED_INVESTIGATION.value,
                    evidence=evidence,
                )

            # If no specific tools required
            return EvaluationScore(
                evaluator_name=self.evaluator_name,
                evaluator_version=self.evaluator_version,
                dimension=self.dimension,
                applicable=True,
                status="pass",
                score=1.0,
                reason_code=ReasonCode.SUCCESS.value,
                evidence=evidence,
            )

        except Exception as exc:
            return EvaluationScore(
                evaluator_name=self.evaluator_name,
                evaluator_version=self.evaluator_version,
                dimension=self.dimension,
                applicable=True,
                status="error",
                score=0.0,
                reason_code=ReasonCode.EVALUATION_ERROR.value,
                evidence={"error": str(exc), "error_type": type(exc).__name__},
            )

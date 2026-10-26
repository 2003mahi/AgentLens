from typing import Any, Dict
from backend.app.evaluation.base import BaseEvaluator, EvaluationContext, EvaluationScore, ReasonCode

class OutcomeEvaluator:
    evaluator_name: str = "outcome_evaluator"
    evaluator_version: str = "1.0.0"
    dimension: str = "outcome"

    def evaluate(self, context: EvaluationContext) -> EvaluationScore:
        try:
            expected_outcome = context.evaluation_spec.get("outcome")
            if not expected_outcome:
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=False,
                    status="not_applicable",
                    score=1.0,
                    reason_code=ReasonCode.SUCCESS.value,
                    evidence={"note": "No outcome requirements specified in evaluation_spec"},
                )

            final_state = context.final_environment_state
            evidence: Dict[str, Any] = {
                "expected": expected_outcome,
                "observed": {
                    "refunded_total_minor": final_state.get("refunded_total_minor", 0),
                    "refunds_count": len(final_state.get("refunds", [])),
                    "ticket_status": final_state.get("ticket_status"),
                },
            }

            # Check refund amount
            if "refund_total_minor" in expected_outcome:
                expected_amount = expected_outcome["refund_total_minor"]
                observed_amount = final_state.get("refunded_total_minor", 0)
                if expected_amount != observed_amount:
                    evidence["mismatch"] = "refund_total_minor"
                    return EvaluationScore(
                        evaluator_name=self.evaluator_name,
                        evaluator_version=self.evaluator_version,
                        dimension=self.dimension,
                        applicable=True,
                        status="fail",
                        score=0.0,
                        reason_code=ReasonCode.WRONG_REFUND_AMOUNT.value,
                        evidence=evidence,
                    )

            # Check ticket status if expected
            if "ticket_status" in expected_outcome:
                expected_ticket = expected_outcome["ticket_status"]
                observed_ticket = final_state.get("ticket_status")
                if expected_ticket != observed_ticket:
                    evidence["mismatch"] = "ticket_status"
                    return EvaluationScore(
                        evaluator_name=self.evaluator_name,
                        evaluator_version=self.evaluator_version,
                        dimension=self.dimension,
                        applicable=True,
                        status="fail",
                        score=0.0,
                        reason_code="TICKET_STATUS_MISMATCH",
                        evidence=evidence,
                    )

            # Check refund count constraint
            expected_refund_count = 1 if expected_outcome.get("refund_total_minor", 0) > 0 else 0
            observed_refund_count = len(final_state.get("refunds", []))
            if expected_refund_count > 0 and observed_refund_count != expected_refund_count:
                evidence["mismatch"] = "refund_count"
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code=ReasonCode.DUPLICATE_OPERATION.value if observed_refund_count > 1 else ReasonCode.WRONG_REFUND_AMOUNT.value,
                    evidence=evidence,
                )

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

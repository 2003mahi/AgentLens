import re
from typing import Any, Dict
from backend.app.evaluation.base import BaseEvaluator, EvaluationContext, EvaluationScore, ReasonCode

class ResponseEvaluator:
    evaluator_name: str = "response_evaluator"
    evaluator_version: str = "1.0.0"
    dimension: str = "response"

    def evaluate(self, context: EvaluationContext) -> EvaluationScore:
        try:
            final_response = context.agent_result.get("final_response", "").strip()
            final_state = context.final_environment_state
            refunds = final_state.get("refunds", [])
            refund_amount = final_state.get("refunded_total_minor", 0)

            evidence: Dict[str, Any] = {
                "final_response": final_response,
                "refunds_count": len(refunds),
                "refunded_total_minor": refund_amount,
            }

            if not final_response:
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code="EMPTY_RESPONSE",
                    evidence=evidence,
                )

            lower_resp = final_response.lower()

            # Claim patterns for successful refund
            claims_refund_done = bool(
                re.search(r"\b(refund(ed| has been issued| processed| granted| completed| of ₹| of rs))\b", lower_resp)
                and not re.search(r"\b(cannot|could not|unable to|not eligible|pending approval|denied|failed)\b", lower_resp)
            )

            # Ground truth: was a refund executed in the environment?
            actually_refunded = len(refunds) > 0 and refund_amount > 0

            if claims_refund_done and not actually_refunded:
                evidence["factual_mismatch"] = "Agent claimed refund was processed, but zero refund was executed in environment."
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code=ReasonCode.RESPONSE_FACTUAL_MISMATCH.value,
                    evidence=evidence,
                )

            # If refund was executed, but agent says it could not be done or failed
            claims_refund_failed = bool(
                re.search(r"\b(cannot issue|unable to refund|denied|not processed)\b", lower_resp)
            )
            if actually_refunded and claims_refund_failed:
                evidence["factual_mismatch"] = "Agent claimed refund failed, but refund was successfully executed in environment."
                return EvaluationScore(
                    evaluator_name=self.evaluator_name,
                    evaluator_version=self.evaluator_version,
                    dimension=self.dimension,
                    applicable=True,
                    status="fail",
                    score=0.0,
                    reason_code=ReasonCode.RESPONSE_FACTUAL_MISMATCH.value,
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

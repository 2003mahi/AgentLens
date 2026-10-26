import time
from typing import Any, Callable, Dict, Optional
from backend.app.evaluation.base import BaseEvaluator, EvaluationContext, EvaluationScore, ReasonCode

class LLMJudgeEvaluator:
    evaluator_name: str = "llm_judge"
    evaluator_version: str = "1.0.0"
    dimension: str = "llm_judge"

    def __init__(
        self,
        provider_fn: Optional[Callable[[str, int], Dict[str, Any]]] = None,
        enabled: bool = False,
        model_name: str = "mock-judge-v1",
        max_tokens: int = 500,
    ):
        self.provider_fn = provider_fn
        self.enabled = enabled
        self.model_name = model_name
        self.max_tokens = max_tokens

    def evaluate(self, context: EvaluationContext) -> EvaluationScore:
        if not self.enabled:
            return EvaluationScore(
                evaluator_name=self.evaluator_name,
                evaluator_version=self.evaluator_version,
                dimension=self.dimension,
                applicable=False,
                status="not_applicable",
                score=1.0,
                reason_code=ReasonCode.SUCCESS.value,
                evidence={"note": "LLM judge evaluation disabled in configuration"},
            )

        try:
            final_response = context.agent_result.get("final_response", "")
            user_message = context.agent_input.get("user_message", "")

            # Judge prompt following rubric (Clarity, Completeness, Tone: 0-2)
            judge_prompt = (
                f"You are an impartial evaluator assessing customer support response quality.\n"
                f"User Request: {user_message}\n"
                f"Agent Response: {final_response}\n\n"
                f"Evaluate on: Clarity (0-2), Completeness (0-2), Tone (0-2)."
            )

            start_t = time.perf_counter()
            if self.provider_fn:
                # Call configured provider
                raw_result = self.provider_fn(judge_prompt, self.max_tokens)
                duration_ms = (time.perf_counter() - start_t) * 1000.0

                clarity = raw_result.get("clarity", 2)
                completeness = raw_result.get("completeness", 2)
                tone = raw_result.get("tone", 2)
                usage = raw_result.get("usage", {})
            else:
                # Deterministic baseline scoring when no provider configured
                duration_ms = (time.perf_counter() - start_t) * 1000.0
                clarity = 2 if len(final_response) > 20 else 1
                completeness = 2 if len(final_response) > 40 else 1
                tone = 2 if "please" in final_response.lower() or "help" in final_response.lower() or "refund" in final_response.lower() else 1
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            total_raw = clarity + completeness + tone
            normalized_score = round(total_raw / 6.0, 3)

            evidence = {
                "clarity": clarity,
                "completeness": completeness,
                "tone": tone,
                "raw_total": total_raw,
                "max_score": 6,
                "judge_model": self.model_name,
                "judge_duration_ms": round(duration_ms, 2),
                "judge_usage": usage,
            }

            return EvaluationScore(
                evaluator_name=self.evaluator_name,
                evaluator_version=self.evaluator_version,
                dimension=self.dimension,
                applicable=True,
                status="pass" if normalized_score >= 0.5 else "fail",
                score=normalized_score,
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

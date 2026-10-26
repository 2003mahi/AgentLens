import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

class ScoreAggregator:
    def __init__(
        self,
        experiment_id: str,
        dataset_version_id: str,
        config_ids: List[str],
        weights: Optional[Dict[str, float]] = None,
    ):
        self.experiment_id = experiment_id
        self.dataset_version_id = dataset_version_id
        self.config_ids = config_ids
        self.weights = weights or {
            "outcome": 0.4,
            "policy": 0.3,
            "trajectory": 0.2,
            "response": 0.1,
        }
        self.scores: List[Dict[str, Any]] = []
        self.attempt_metadata: List[Dict[str, Any]] = []
        self.usage_records: List[Dict[str, Any]] = []

    def add_attempt_result(
        self,
        attempt_id: str,
        run_id: str,
        agent_config_id: str,
        task_id: str,
        scores: List[Dict[str, Any]],
        usage: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        environment_id: Optional[str] = None,
    ) -> None:
        self.attempt_metadata.append({
            "attempt_id": attempt_id,
            "run_id": run_id,
            "agent_config_id": agent_config_id,
            "task_id": task_id,
            "environment_id": environment_id,
            "duration_ms": duration_ms or 0.0,
        })
        for s in scores:
            score_item = dict(s)
            score_item["attempt_id"] = attempt_id
            score_item["run_id"] = run_id
            score_item["agent_config_id"] = agent_config_id
            score_item["task_id"] = task_id
            self.scores.append(score_item)

        if usage:
            self.usage_records.append(usage)

    def aggregate(self) -> Dict[str, Any]:
        dimensions: Dict[str, List[float]] = {}
        dimension_pass: Dict[str, int] = {}
        dimension_counts: Dict[str, int] = {}
        reason_codes: Dict[str, int] = {}
        evaluator_versions: Dict[str, str] = {}

        for s in self.scores:
            dim = s.get("dimension", "unknown")
            eval_name = s.get("evaluator_name", "unknown")
            eval_ver = s.get("evaluator_version", "unknown")
            evaluator_versions[eval_name] = eval_ver

            applicable = s.get("applicable", True)
            if not applicable:
                continue

            score = float(s.get("score", 0.0))
            status = s.get("status", "fail")
            reason = s.get("reason_code")

            dimensions.setdefault(dim, []).append(score)
            dimension_counts[dim] = dimension_counts.get(dim, 0) + 1
            if status == "pass":
                dimension_pass[dim] = dimension_pass.get(dim, 0) + 1

            if reason:
                reason_codes[reason] = reason_codes.get(reason, 0) + 1

        dimension_metrics = {}
        weighted_sum = 0.0
        weight_normalizer = 0.0

        for dim, vals in dimensions.items():
            mean_score = sum(vals) / len(vals) if vals else 0.0
            total_cnt = dimension_counts.get(dim, 0)
            pass_cnt = dimension_pass.get(dim, 0)
            pass_rate = pass_cnt / total_cnt if total_cnt > 0 else 0.0

            dimension_metrics[dim] = {
                "mean_score": round(mean_score, 4),
                "pass_rate": round(pass_rate, 4),
                "pass_count": pass_cnt,
                "total_count": total_cnt,
            }

            weight = self.weights.get(dim, 0.0)
            if weight > 0:
                weighted_sum += mean_score * weight
                weight_normalizer += weight

        overall_composite = (
            round(weighted_sum / weight_normalizer, 4) if weight_normalizer > 0 else 0.0
        )

        # Aggregate observed usage and latency
        total_prompt_tokens = sum(u.get("prompt_tokens", 0) for u in self.usage_records)
        total_completion_tokens = sum(u.get("completion_tokens", 0) for u in self.usage_records)
        total_tokens = sum(u.get("total_tokens", 0) for u in self.usage_records)
        total_estimated_cost = sum(u.get("estimated_cost_usd", 0.0) for u in self.usage_records)
        total_duration_ms = sum(m.get("duration_ms", 0.0) for m in self.attempt_metadata)

        reproducibility = {
            "experiment_id": self.experiment_id,
            "dataset_version_id": self.dataset_version_id,
            "config_ids": self.config_ids,
            "total_attempts": len(self.attempt_metadata),
            "evaluator_versions": evaluator_versions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "experiment_id": self.experiment_id,
            "composite_score": overall_composite,
            "overall_score": overall_composite,
            "total_attempts": len(self.attempt_metadata),
            "dimension_averages": {dim: metrics["mean_score"] for dim, metrics in dimension_metrics.items()},
            "reproducibility": reproducibility,
            "dimension_scores": dimension_metrics,
            "failure_reasons": reason_codes,
            "resource_usage": {
                "total_duration_ms": round(total_duration_ms, 2),
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost_usd": round(total_estimated_cost, 6),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.aggregate(), indent=indent)

    def to_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "attempt_id",
            "run_id",
            "agent_config_id",
            "task_id",
            "evaluator_name",
            "dimension",
            "status",
            "score",
            "reason_code",
        ])
        for s in self.scores:
            writer.writerow([
                s.get("attempt_id"),
                s.get("run_id"),
                s.get("agent_config_id"),
                s.get("task_id"),
                s.get("evaluator_name"),
                s.get("dimension"),
                s.get("status"),
                s.get("score"),
                s.get("reason_code"),
            ])
        return output.getvalue()

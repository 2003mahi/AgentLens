import time
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.app.db.models import Run, Attempt, Score, Job, Experiment, TaskVersion, AgentConfig, generate_uuid
from backend.app.evaluation.base import BaseEvaluator, EvaluationContext, EvaluationScore, ReasonCode
from backend.app.evaluation.outcome import OutcomeEvaluator
from backend.app.evaluation.policy import PolicyEvaluator
from backend.app.evaluation.trajectory import TrajectoryEvaluator
from backend.app.evaluation.response import ResponseEvaluator
from backend.app.evaluation.llm_judge import LLMJudgeEvaluator
from backend.app.evaluation.aggregator import ScoreAggregator
from backend.app.execution.environment import MockEnvironment
from backend.app.execution.tools import ToolGateway
from backend.app.execution.traces import TraceRecorder
from backend.app.execution.adapters.base import AgentAdapter, AgentLimits, AgentResult
from backend.app.execution.adapters.scripted import ScriptedAgentAdapter
from backend.app.execution.adapters.tool_loop import ToolLoopAgentAdapter

class EvaluationEngine:
    def __init__(
        self,
        db: Session,
        evaluators: Optional[List[BaseEvaluator]] = None,
        llm_judge_enabled: bool = False,
    ):
        self.db = db
        self.llm_judge_enabled = llm_judge_enabled
        self.evaluators: List[BaseEvaluator] = evaluators or [
            OutcomeEvaluator(),
            PolicyEvaluator(),
            TrajectoryEvaluator(),
            ResponseEvaluator(),
            LLMJudgeEvaluator(enabled=llm_judge_enabled),
        ]

    async def execute_run(self, run: Run) -> Dict[str, Any]:
        """Executes a single Run end-to-end: attempt lifecycle, trace recording, and evaluation."""
        start_time = time.perf_counter()
        task: TaskVersion = run.task_version if hasattr(run, "task_version") and run.task_version else (
            self.db.query(TaskVersion).filter(TaskVersion.id == run.task_version_id).first()
        )
        config: AgentConfig = run.agent_config if hasattr(run, "agent_config") and run.agent_config else (
            self.db.query(AgentConfig).filter(AgentConfig.id == run.agent_config_id).first()
        )

        if not task or not config:
            raise ValueError(f"Task or AgentConfig missing for Run {run.id}")

        # Update run status
        setattr(run, "execution_status", "running")
        self.db.flush()

        # 1. Create Attempt with unique environment_id
        environment_id = generate_uuid()
        attempt_number = self.db.query(Attempt).filter(Attempt.run_id == run.id).count() + 1
        attempt = Attempt(
            run_id=run.id,
            attempt_number=attempt_number,
            environment_id=environment_id,
            status="running",
        )
        self.db.add(attempt)
        self.db.flush()

        # 2. Setup Isolated Environment and Trace Recorder
        env = MockEnvironment(
            environment_id=environment_id,
            fixture=task.environment_fixture or {},
            reviewer_behavior=task.reviewer_behavior or {},
        )
        recorder = TraceRecorder(attempt_id=attempt.id, db=self.db)

        # 3. Record Reproducibility Metadata and Attempt Start
        evaluator_versions = {ev.evaluator_name: ev.evaluator_version for ev in self.evaluators}
        reproducibility = {
            "run_id": run.id,
            "experiment_id": run.experiment_id,
            "agent_config_id": config.id,
            "agent_model": config.model,
            "task_version_id": task.id,
            "task_id": task.task_id,
            "environment_id": environment_id,
            "evaluator_versions": evaluator_versions,
        }
        recorder.record_event(
            event_type="reproducibility_metadata",
            status="info",
            payload=reproducibility,
        )
        recorder.record_event(
            event_type="attempt_start",
            status="started",
            payload={"task_id": task.task_id, "repetition": run.repetition},
        )

        # 4. Resolve Agent Adapter
        auth_cust = (task.agent_input or {}).get("authenticated_customer_id")
        tool_gateway = ToolGateway(
            environment=env,
            authenticated_customer_id=auth_cust,
            recorder=recorder,
            allowed_tools=config.tools or None,
        )

        limits_dict = (task.evaluation_spec or {}).get("limits", {})
        limits = AgentLimits(
            max_model_turns=limits_dict.get("max_model_turns", 12),
            max_tool_calls=limits_dict.get("max_tool_calls", 20),
            timeout_seconds=limits_dict.get("timeout_seconds", 60.0),
        )

        agent_result: AgentResult
        try:
            adapter = self._resolve_adapter(config, task)
            agent_result = await adapter.run(
                task_input=task.agent_input or {},
                tool_gateway=tool_gateway,
                recorder=recorder,
                limits=limits,
            )
            setattr(run, "execution_status", "completed")
        except Exception as exc:
            setattr(run, "execution_status", "failed")
            recorder.record_event(
                event_type="error",
                status="failed",
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            agent_result = AgentResult(
                final_response="",
                stop_reason="error",
                metadata={"error": str(exc)},
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        final_state = env.get_final_state()

        recorder.record_event(
            event_type="attempt_finish",
            duration_ms=duration_ms,
            status=getattr(run, "execution_status", "unknown"),
            payload={
                "stop_reason": agent_result.stop_reason,
                "final_response": agent_result.final_response,
                "usage": agent_result.usage,
            },
        )

        # 5. Run Evaluators
        setattr(run, "evaluation_status", "running")
        self.db.flush()

        eval_ctx = EvaluationContext(
            task_id=task.task_id,
            task_version=task.version,
            agent_input=task.agent_input or {},
            environment_fixture=task.environment_fixture or {},
            evaluation_spec=task.evaluation_spec or {},
            final_environment_state=final_state,
            trace_events=recorder.get_events(),
            agent_result={
                "final_response": agent_result.final_response,
                "stop_reason": agent_result.stop_reason,
                "usage": agent_result.usage,
                "metadata": agent_result.metadata,
            },
            metadata=reproducibility,
        )

        scores_out: List[Score] = []
        for evaluator in self.evaluators:
            res: EvaluationScore = evaluator.evaluate(eval_ctx)
            db_score = Score(
                attempt_id=attempt.id,
                evaluator_name=res.evaluator_name,
                evaluator_version=res.evaluator_version,
                dimension=res.dimension,
                applicable=res.applicable,
                status=res.status,
                score=res.score,
                reason_code=res.reason_code,
                evidence=res.evidence,
            )
            self.db.add(db_score)
            scores_out.append(db_score)

        setattr(attempt, "status", "completed")
        setattr(run, "evaluation_status", "completed")

        # Update Job if exists
        job = self.db.query(Job).filter(Job.run_id == run.id, Job.status == "queued").first()
        if job:
            setattr(job, "status", "completed")

        self.db.commit()

        return {
            "run_id": run.id,
            "attempt_id": attempt.id,
            "environment_id": environment_id,
            "execution_status": run.execution_status,
            "evaluation_status": run.evaluation_status,
            "duration_ms": duration_ms,
            "agent_result": {
                "final_response": agent_result.final_response,
                "stop_reason": agent_result.stop_reason,
                "usage": agent_result.usage,
            },
            "scores": [
                {
                    "evaluator_name": s.evaluator_name,
                    "evaluator_version": s.evaluator_version,
                    "dimension": s.dimension,
                    "applicable": s.applicable,
                    "status": s.status,
                    "score": s.score,
                    "reason_code": s.reason_code,
                    "evidence": s.evidence,
                }
                for s in scores_out
            ],
            "reproducibility": reproducibility,
        }

    async def execute_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """Executes all runs of an experiment and returns aggregated summary."""
        exp = self.db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        setattr(exp, "status", "running")
        self.db.commit()

        runs = self.db.query(Run).filter(Run.experiment_id == experiment_id).all()
        aggregator = ScoreAggregator(
            experiment_id=exp.id,
            dataset_version_id=exp.dataset_version_id,
            config_ids=exp.config_ids or [],
        )

        for run in runs:
            res = await self.execute_run(run)
            aggregator.add_attempt_result(
                attempt_id=res["attempt_id"],
                run_id=res["run_id"],
                agent_config_id=run.agent_config_id,
                task_id=res["reproducibility"]["task_id"],
                scores=res["scores"],
                usage=res["agent_result"]["usage"],
                duration_ms=res["duration_ms"],
                environment_id=res["environment_id"],
            )

        setattr(exp, "status", "completed")
        self.db.commit()

        summary = aggregator.aggregate()
        return summary

    def _resolve_adapter(self, config: AgentConfig, task: TaskVersion) -> AgentAdapter:
        if config.adapter == "scripted":
            # Check limits/name/metadata for designated scripted mode
            limits_data = config.limits or {}
            mode = limits_data.get("scripted_mode")
            if not mode:
                # Infer from agent config name if available
                cfg_name = config.name.lower()
                if "unauthorized" in cfg_name or "access" in cfg_name:
                    mode = "unauthorized"
                elif "missing_approval" in cfg_name or "unapproved" in cfg_name:
                    mode = "missing_approval"
                elif "deceptive" in cfg_name or "fake" in cfg_name:
                    mode = "deceptive"
                elif "wrong_amount" in cfg_name:
                    mode = "wrong_amount"
                elif "duplicate" in cfg_name:
                    mode = "duplicate_refund"
                else:
                    mode = "perfect"
            return ScriptedAgentAdapter(mode=mode)

        elif config.adapter == "tool_loop":
            return ToolLoopAgentAdapter(
                model_name=config.model,
                system_prompt=config.system_prompt,
            )

        return ScriptedAgentAdapter(mode="perfect")

import time
from typing import Any, Callable, Dict, List, Optional
from backend.app.execution.adapters.base import AgentAdapter, AgentLimits, AgentResult

class ToolLoopAgentAdapter:
    """Bounded, testable agent tool loop that interacts with a model provider and tool gateway."""

    def __init__(
        self,
        model_name: str = "mock-agent-v1",
        system_prompt: str = "You are a customer support agent.",
        provider_fn: Optional[Callable[[List[Dict[str, Any]], List[Dict[str, Any]]], Dict[str, Any]]] = None,
    ):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.provider_fn = provider_fn

    async def run(
        self,
        task_input: Dict[str, Any],
        tool_gateway: Any,
        recorder: Any,
        limits: Optional[AgentLimits] = None,
    ) -> AgentResult:
        lim = limits or AgentLimits()
        start_time = time.perf_counter()

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task_input.get("user_message", "")},
        ]

        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tool_calls = 0

        for turn in range(lim.max_model_turns):
            # Check timeout
            elapsed = time.perf_counter() - start_time
            if elapsed > lim.timeout_seconds:
                return AgentResult(
                    final_response="",
                    stop_reason="timeout",
                    usage={
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                    },
                )

            # Generate model call
            recorder.record_event(
                event_type="model_request",
                status="pending",
                payload={"model": self.model_name, "turn": turn + 1, "messages_count": len(messages)},
            )

            model_out: Dict[str, Any]
            if self.provider_fn:
                model_out = self.provider_fn(messages, tool_gateway.visible_schemas())
            else:
                # Default mock generator: does a simple get_order then final message
                if turn == 0:
                    model_out = {
                        "text": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "name": "get_order",
                                "arguments": {"order_id": task_input.get("order_id", "ord_1042")},
                            }
                        ],
                        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
                    }
                else:
                    model_out = {
                        "text": "Thank you for contacting us. I found your order details.",
                        "tool_calls": [],
                        "usage": {"prompt_tokens": 80, "completion_tokens": 30},
                    }

            raw_usage = model_out.get("usage")
            usage: Dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
            p_tok = int(usage.get("prompt_tokens", 0))
            c_tok = int(usage.get("completion_tokens", 0))
            total_prompt_tokens += p_tok
            total_completion_tokens += c_tok

            raw_tool_calls = model_out.get("tool_calls")
            tool_calls: List[Dict[str, Any]] = [c for c in raw_tool_calls if isinstance(c, dict)] if isinstance(raw_tool_calls, list) else []

            recorder.record_event(
                event_type="model_response",
                status="success",
                payload={
                    "text": model_out.get("text"),
                    "tool_calls": tool_calls,
                    "usage": usage,
                },
            )

            if not tool_calls:
                final_text = str(model_out.get("text") or "")
                return AgentResult(
                    final_response=final_text,
                    stop_reason="model_final",
                    usage={
                        "prompt_tokens": total_prompt_tokens,
                        "completion_tokens": total_completion_tokens,
                        "total_tokens": total_prompt_tokens + total_completion_tokens,
                        "estimated_cost_usd": round((total_prompt_tokens * 0.0000015) + (total_completion_tokens * 0.000002), 6),
                    },
                )

            # Execute tool calls
            for call in tool_calls:
                if total_tool_calls >= lim.max_tool_calls:
                    return AgentResult(
                        final_response="Tool budget exceeded.",
                        stop_reason="max_tool_calls",
                        usage={
                            "prompt_tokens": total_prompt_tokens,
                            "completion_tokens": total_completion_tokens,
                            "total_tokens": total_prompt_tokens + total_completion_tokens,
                        },
                    )

                total_tool_calls += 1
                tool_name = str(call.get("name") or "")
                raw_arguments = call.get("arguments", {})
                if not isinstance(raw_arguments, dict):
                    raw_arguments = {}
                tool_call_id = str(call.get("id") or "")

                res = await tool_gateway.execute(
                    tool_name=tool_name,
                    raw_arguments=raw_arguments,
                    tool_call_id=tool_call_id,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": res,
                })

        return AgentResult(
            final_response="",
            stop_reason="max_turns",
            usage={
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
            },
        )

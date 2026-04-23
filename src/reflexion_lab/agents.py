from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .mock_runtime import failure_mode_for_qid
from .runtime import MockRuntime, RuntimeAdapter
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord


@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    runtime: RuntimeAdapter = field(default_factory=MockRuntime)

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0

        for attempt_id in range(1, self.max_attempts + 1):
            actor_result = self.runtime.actor_answer(
                example=example,
                attempt_id=attempt_id,
                agent_type=self.agent_type,
                reflection_memory=reflection_memory,
            )
            evaluator_result = self.runtime.evaluator(example=example, answer=actor_result.answer)
            judge = evaluator_result.judge
            token_estimate = actor_result.token_count + evaluator_result.token_count
            latency_ms = actor_result.latency_ms + evaluator_result.latency_ms

            trace = AttemptTrace(
                attempt_id=attempt_id,
                answer=actor_result.answer,
                score=judge.score,
                reason=judge.reason,
                token_estimate=token_estimate,
                latency_ms=latency_ms,
            )
            final_answer = actor_result.answer
            final_score = judge.score

            if judge.score == 1:
                traces.append(trace)
                break

            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                reflector_result = self.runtime.reflector(
                    example=example,
                    attempt_id=attempt_id,
                    judge=judge,
                )
                reflection = reflector_result.reflection
                reflections.append(reflection)
                trace.reflection = reflection
                trace.token_estimate += reflector_result.token_count
                trace.latency_ms += reflector_result.latency_ms
                # Keep memory compact and actionable for the next actor turn.
                reflection_memory.append(
                    f"Lesson: {reflection.lesson} Strategy: {reflection.next_strategy}"
                )

            traces.append(trace)

        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = (
            "none"
            if final_score == 1
            else failure_mode_for_qid(example.qid)
        )

        return RunRecord(
            qid=example.qid,
            question=example.question,
            gold_answer=example.gold_answer,
            agent_type=self.agent_type,
            predicted_answer=final_answer,
            is_correct=bool(final_score),
            attempts=len(traces),
            token_estimate=total_tokens,
            latency_ms=total_latency,
            failure_mode=failure_mode,
            reflections=reflections,
            traces=traces,
        )


class ReActAgent(BaseAgent):
    def __init__(self, runtime: RuntimeAdapter | None = None) -> None:
        super().__init__(agent_type="react", max_attempts=1, runtime=runtime or MockRuntime())


class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, runtime: RuntimeAdapter | None = None) -> None:
        super().__init__(
            agent_type="reflexion",
            max_attempts=max_attempts,
            runtime=runtime or MockRuntime(),
        )

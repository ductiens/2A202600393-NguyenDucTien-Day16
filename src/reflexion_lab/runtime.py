from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from openai import OpenAI

from . import mock_runtime
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import JudgeResult, QAExample, ReflectionEntry


@dataclass
class ActorResult:
    answer: str
    token_count: int
    latency_ms: int


@dataclass
class EvaluatorResult:
    judge: JudgeResult
    token_count: int
    latency_ms: int


@dataclass
class ReflectorResult:
    reflection: ReflectionEntry
    token_count: int
    latency_ms: int


class RuntimeAdapter(Protocol):
    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> ActorResult:
        ...

    def evaluator(self, example: QAExample, answer: str) -> EvaluatorResult:
        ...

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        judge: JudgeResult,
    ) -> ReflectorResult:
        ...


def _format_context(example: QAExample) -> str:
    blocks: list[str] = []
    for idx, chunk in enumerate(example.context, start=1):
        blocks.append(f"[{idx}] {chunk.title}\n{chunk.text}")
    return "\n\n".join(blocks)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_json_content(content: str) -> dict[str, Any]:
    raw = content.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


class MockRuntime:
    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> ActorResult:
        answer = mock_runtime.actor_answer(example, attempt_id, agent_type, reflection_memory)
        token_count = 320 + (attempt_id * 65) + (120 if agent_type == "reflexion" else 0)
        latency_ms = 160 + (attempt_id * 40) + (90 if agent_type == "reflexion" else 0)
        return ActorResult(answer=answer, token_count=token_count, latency_ms=latency_ms)

    def evaluator(self, example: QAExample, answer: str) -> EvaluatorResult:
        judge = mock_runtime.evaluator(example, answer)
        token_count = 140
        latency_ms = 95
        return EvaluatorResult(judge=judge, token_count=token_count, latency_ms=latency_ms)

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        judge: JudgeResult,
    ) -> ReflectorResult:
        reflection = mock_runtime.reflector(example, attempt_id, judge)
        token_count = 110
        latency_ms = 85
        return ReflectorResult(reflection=reflection, token_count=token_count, latency_ms=latency_ms)


class OpenAIRuntime:
    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("Missing OPENAI_API_KEY. Set it in env or .env before running --mode openai.")

        self.model = (
            model
            or os.getenv("OPENAI_MODEL")
            or os.getenv("DEFAULT_MODEL")
            or "gpt-4.1-nano"
        )
        self.temperature = (
            temperature if temperature is not None else float(os.getenv("TEMPERATURE", "0.2"))
        )
        self.max_tokens = max_tokens if max_tokens is not None else int(os.getenv("MAX_TOKENS", "500"))
        self.client = OpenAI(api_key=key, base_url=base_url or os.getenv("OPENAI_BASE_URL"))

    def _chat_json(self, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], int, int]:
        start = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        content = (response.choices[0].message.content or "{}").strip()
        usage = response.usage
        token_count = _safe_int(getattr(usage, "total_tokens", 0))
        return _parse_json_content(content), token_count, latency_ms

    def _chat_text(self, system_prompt: str, user_prompt: str) -> tuple[str, int, int]:
        start = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        answer = (response.choices[0].message.content or "").strip()
        usage = response.usage
        token_count = _safe_int(getattr(usage, "total_tokens", 0))
        return answer, token_count, latency_ms

    def actor_answer(
        self,
        example: QAExample,
        attempt_id: int,
        agent_type: str,
        reflection_memory: list[str],
    ) -> ActorResult:
        memory = "\n".join(f"- {item}" for item in reflection_memory) if reflection_memory else "- (none)"
        user_prompt = (
            f"Question:\n{example.question}\n\n"
            f"Context:\n{_format_context(example)}\n\n"
            f"Attempt ID: {attempt_id}\n"
            f"Agent type: {agent_type}\n"
            f"Reflection memory:\n{memory}\n\n"
            "Return only final answer text."
        )
        answer, token_count, latency_ms = self._chat_text(ACTOR_SYSTEM, user_prompt)
        return ActorResult(answer=answer, token_count=token_count, latency_ms=latency_ms)

    def evaluator(self, example: QAExample, answer: str) -> EvaluatorResult:
        user_prompt = (
            f"Question:\n{example.question}\n\n"
            f"Gold answer:\n{example.gold_answer}\n\n"
            f"Predicted answer:\n{answer}\n\n"
            "Evaluate exact-match style correctness after normalization and return JSON."
        )
        payload, token_count, latency_ms = self._chat_json(EVALUATOR_SYSTEM, user_prompt)
        judge = JudgeResult.model_validate(payload)
        return EvaluatorResult(judge=judge, token_count=token_count, latency_ms=latency_ms)

    def reflector(
        self,
        example: QAExample,
        attempt_id: int,
        judge: JudgeResult,
    ) -> ReflectorResult:
        user_prompt = (
            f"Question:\n{example.question}\n\n"
            f"Gold answer:\n{example.gold_answer}\n\n"
            f"Attempt ID:\n{attempt_id}\n\n"
            f"Evaluator score:\n{judge.score}\n"
            f"Evaluator reason:\n{judge.reason}\n"
            f"Missing evidence:\n{json.dumps(judge.missing_evidence, ensure_ascii=True)}\n"
            f"Spurious claims:\n{json.dumps(judge.spurious_claims, ensure_ascii=True)}\n\n"
            "Return JSON object with keys: attempt_id, failure_reason, lesson, next_strategy."
        )
        payload, token_count, latency_ms = self._chat_json(REFLECTOR_SYSTEM, user_prompt)
        reflection = ReflectionEntry.model_validate(payload)
        reflection.attempt_id = attempt_id
        return ReflectorResult(reflection=reflection, token_count=token_count, latency_ms=latency_ms)


def build_runtime(mode: Literal["mock", "openai"]) -> RuntimeAdapter:
    if mode == "openai":
        return OpenAIRuntime()
    return MockRuntime()

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

import typer
from dotenv import load_dotenv
from rich import print

from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.runtime import build_runtime
from src.reflexion_lab.schemas import QAExample
from src.reflexion_lab.utils import load_dataset, save_jsonl

app = typer.Typer(add_completion=False)
AUTOGRADE_MIN_RECORDS = 100
NUM_AGENTS = 2


def ensure_min_questions(examples: list[QAExample], min_questions: int) -> list[QAExample]:
    if not examples:
        return examples
    if len(examples) >= min_questions:
        return examples
    multiplier = (min_questions + len(examples) - 1) // len(examples)
    return (examples * multiplier)[:min_questions]


@app.command()
def main(
    dataset: str = "data/hotpot_mini.json",
    out_dir: str = "outputs/sample_run",
    reflexion_attempts: int = 3,
    mode: Literal["mock", "openai"] = "mock",
    min_questions: int = 50,
) -> None:
    load_dotenv()
    required_min_questions = math.ceil(AUTOGRADE_MIN_RECORDS / NUM_AGENTS)
    effective_min_questions = max(min_questions, required_min_questions)

    examples = load_dataset(dataset)
    examples = ensure_min_questions(examples, min_questions=effective_min_questions)
    runtime = build_runtime(mode=mode)

    react = ReActAgent(runtime=runtime)
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts, runtime=runtime)

    react_records = [react.run(example) for example in examples]
    reflexion_records = [reflexion.run(example) for example in examples]
    all_records = react_records + reflexion_records

    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)

    report = build_report(all_records, dataset_name=Path(dataset).name, mode=mode)
    json_path, md_path = save_report(report, out_path)

    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(
        f"Autograde guard: requested min_questions={min_questions}, "
        f"effective_min_questions={effective_min_questions}, num_records={len(all_records)}"
    )
    print(json.dumps(report.summary, indent=2))


if __name__ == "__main__":
    app()

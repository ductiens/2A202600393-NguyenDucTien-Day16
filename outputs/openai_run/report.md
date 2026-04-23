# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_mini.json
- Mode: openai
- Records: 100
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.98 | 1.0 | 0.02 |
| Avg attempts | 1 | 1 | 0 |
| Avg token estimate | 396.08 | 397.52 | 1.44 |
| Avg latency (ms) | 3091.44 | 1833.4 | -1258.04 |

## Failure modes
```json
{
  "react": {
    "none": 49,
    "wrong_final_answer": 1
  },
  "reflexion": {
    "none": 50
  },
  "overall": {
    "none": 99,
    "wrong_final_answer": 1
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
Reflexion improves robustness in multi-hop QA when first-pass reasoning is incomplete or drifts to a wrong second-hop entity. In this run, ReAct keeps lower latency and lower token cost, while Reflexion trades extra attempts for higher correction rate on failure-prone questions. The most useful reflections are concise and operational, because they convert vague feedback into a concrete next strategy for the Actor. Remaining errors typically come from insufficient grounding in the second hop or from evaluator blind spots. In a production setup, quality can be improved further by stronger evaluator structure, memory compression, and adaptive attempt budgets calibrated by confidence.

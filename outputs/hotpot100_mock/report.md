# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_100.json
- Mode: mock
- Records: 200
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.5 | 1.0 | 0.5 |
| Avg attempts | 1 | 1.5 | 0.5 |
| Avg token estimate | 525 | 1055 | 530 |
| Avg latency (ms) | 295 | 640 | 345 |

## Failure modes
```json
{
  "react": {
    "none": 50,
    "incomplete_multi_hop": 13,
    "wrong_final_answer": 13,
    "entity_drift": 24
  },
  "reflexion": {
    "none": 100
  },
  "overall": {
    "none": 150,
    "incomplete_multi_hop": 13,
    "wrong_final_answer": 13,
    "entity_drift": 24
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

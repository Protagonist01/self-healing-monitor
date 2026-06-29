# Evaluation

Evaluation is intentionally deterministic in this repo so it can run without paid LLM calls.

```powershell
make eval
```

or:

```powershell
.\healer\.venv\Scripts\python.exe evals\run_evals.py
```

The runner reads `evals/scenarios.jsonl`, passes each fixture through the action planner and policy gate, and writes `evals/results/latest.json`.

## Metrics

| Metric | Meaning |
| --- | --- |
| Action accuracy | selected action matches the fixture expectation |
| Policy gate correctness | auto vs human routing matches the fixture expectation |

## Adding Scenarios

Append a JSON line to `evals/scenarios.jsonl`:

```json
{"id":"example","alert_name":"HighMemoryUsage","service":"api","root_cause":"OOMKilled after memory leak","confidence":0.86,"expected_action":"RESTART_CONTAINER","expected_policy":"auto_execute"}
```

Live LLM quality should be evaluated separately by capturing real incident outputs and adding them as fixtures after review.

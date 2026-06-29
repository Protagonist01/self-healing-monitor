import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from healer.src.agent.nodes.action_planner import action_planner_node
from healer.src.agent.nodes.policy_gate import policy_gate_node


ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios.jsonl"
RESULTS_DIR = ROOT / "results"


def make_state(scenario):
    return {
        "incident_id": scenario["id"],
        "alert": {
            "name": scenario["alert_name"],
            "service": scenario["service"],
            "severity": "warning",
            "labels": {"alertname": scenario["alert_name"], "service": scenario["service"]},
            "annotations": {},
            "received_at": "2026-06-23T22:00:00+00:00",
        },
        "context": None,
        "diagnosis": {
            "root_cause": scenario["root_cause"],
            "confidence": scenario["confidence"],
            "supporting_evidence": ["scenario fixture"],
            "llm_model": "eval-fixture",
            "llm_tokens_used": 0,
        },
        "action_plan": None,
        "selected_action": None,
        "policy_gate": None,
        "execution": None,
        "retry_count": 0,
        "errors": [],
    }


def main():
    scenarios = [json.loads(line) for line in SCENARIOS.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []

    for scenario in scenarios:
        state = policy_gate_node(action_planner_node(make_state(scenario)))
        action_ok = state["selected_action"] == scenario["expected_action"]
        policy_ok = state["policy_gate"]["decision"] == scenario["expected_policy"]
        results.append(
            {
                "id": scenario["id"],
                "selected_action": state["selected_action"],
                "expected_action": scenario["expected_action"],
                "policy_decision": state["policy_gate"]["decision"],
                "expected_policy": scenario["expected_policy"],
                "action_ok": action_ok,
                "policy_ok": policy_ok,
            }
        )

    action_accuracy = sum(item["action_ok"] for item in results) / len(results)
    policy_accuracy = sum(item["policy_ok"] for item in results) / len(results)
    output = {
        "scenario_count": len(results),
        "action_accuracy": action_accuracy,
        "policy_gate_correctness": policy_accuracy,
        "results": results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "latest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Scenarios: {len(results)}")
    print(f"Action accuracy: {action_accuracy:.0%}")
    print(f"Policy gate correctness: {policy_accuracy:.0%}")
    print(f"Wrote {RESULTS_DIR / 'latest.json'}")


if __name__ == "__main__":
    main()

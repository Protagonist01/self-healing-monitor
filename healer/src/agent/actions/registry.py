"""
Configurable action registry.

Defines the available remediation actions, their impact levels, and the
executor mapping. This replaces the hardcoded action set in the action
planner and graph, making it possible to add new actions via configuration.
"""

from typing import Dict, Any, List


DEFAULT_ACTION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "RESTART_CONTAINER": {
        "impact": "low",
        "executor": "docker",
        "method": "restart_container",
        "description": "Restart the service container to clear transient issues.",
    },
    "SCALE_REPLICAS": {
        "impact": "medium",
        "executor": "docker",
        "method": "scale_replicas",
        "description": "Scale the service to more replicas to distribute load.",
    },
    "ROLLBACK_DEPLOY": {
        "impact": "high",
        "executor": "k8s",
        "method": "rollback_deployment",
        "description": "Rollback to the previous deployment version.",
    },
    "NOTIFY_ONLY": {
        "impact": "low",
        "executor": "notify",
        "method": "notify",
        "description": "Send a notification to operators without taking action.",
    },
}

# Keyword-to-action mapping used by the action planner
DEFAULT_KEYWORD_MAP: List[Dict[str, Any]] = [
    {
        "keywords": ["oom", "memory", "leak"],
        "actions": [
            {
                "action": "RESTART_CONTAINER",
                "impact": "low",
                "reasoning": "Reclaim memory by restarting the container.",
            },
            {
                "action": "SCALE_REPLICAS",
                "impact": "medium",
                "reasoning": "Distribute load to slow memory accumulation.",
            },
            {
                "action": "ROLLBACK_DEPLOY",
                "impact": "high",
                "reasoning": "Rollback if a memory leak was introduced recently.",
            },
        ],
    },
    {
        "keywords": ["500", "bug", "exception", "code", "error"],
        "actions": [
            {
                "action": "ROLLBACK_DEPLOY",
                "impact": "high",
                "reasoning": "Rollback the deployment that introduced a bug.",
            },
            {
                "action": "RESTART_CONTAINER",
                "impact": "low",
                "reasoning": "Restart to clear corrupted application state.",
            },
        ],
    },
    {
        "keywords": ["traffic", "load", "spike", "request"],
        "actions": [
            {
                "action": "SCALE_REPLICAS",
                "impact": "medium",
                "reasoning": "Scale up to handle elevated traffic.",
            },
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Notify operators for capacity planning.",
            },
        ],
    },
    {
        "keywords": ["disk", "storage", "full"],
        "actions": [
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Notify operators — disk cleanup requires manual intervention.",
            },
        ],
    },
    {
        "keywords": ["cert", "certificate", "tls", "ssl", "expired"],
        "actions": [
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Notify operators — certificate renewal required.",
            },
        ],
    },
]


def get_action_registry() -> Dict[str, Dict[str, Any]]:
    """Returns the action registry. Can be extended via configuration in the future."""
    return DEFAULT_ACTION_REGISTRY


def get_keyword_map() -> List[Dict[str, Any]]:
    """Returns the keyword-to-action mapping."""
    return DEFAULT_KEYWORD_MAP


def get_action_impact(action: str) -> str:
    """Returns the impact level for a given action name."""
    registry = get_action_registry()
    entry = registry.get(action)
    return entry["impact"] if entry else "low"

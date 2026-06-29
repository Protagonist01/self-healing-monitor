from typing import TypedDict, List, Dict, Any, Optional, NotRequired

class AlertData(TypedDict):
    name: str
    service: str
    severity: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    received_at: str

class GatheredContext(TypedDict):
    metrics_window_minutes: int
    metrics_summary: str
    metrics_raw: List[Dict[str, Any]]
    log_lines_count: int
    log_summary: str
    log_raw: List[str]
    recent_deploys: List[str]
    runbook_matched: str
    runbook_excerpt: str

class DiagnosisData(TypedDict):
    root_cause: str
    confidence: float
    supporting_evidence: List[str]
    llm_model: str
    llm_tokens_used: int

class PlannedAction(TypedDict):
    action: str  # RESTART_CONTAINER, SCALE_REPLICAS, ROLLBACK_DEPLOY, NOTIFY_ONLY
    impact: str  # low, medium, high
    reasoning: str

class PolicyGateDecision(TypedDict):
    decision: str  # auto_execute, human_approval, notify_only
    checks: Dict[str, Any]  # Details of each check

class ExecutionData(TypedDict):
    status: str  # success, failure, pending, skipped
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    output: str
    alert_resolved: bool

class HealerState(TypedDict):
    incident_id: str
    alert: AlertData
    context: Optional[GatheredContext]
    diagnosis: Optional[DiagnosisData]
    action_plan: Optional[List[PlannedAction]]
    selected_action: Optional[str]
    policy_gate: Optional[PolicyGateDecision]
    execution: Optional[ExecutionData]
    retry_count: NotRequired[int]
    errors: List[str]
